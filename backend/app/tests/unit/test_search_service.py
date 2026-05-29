import uuid
from types import SimpleNamespace

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.db.models import MediaAsset
from app.services import search_service


def make_media(**overrides: object) -> SimpleNamespace:
    data = {
        "id": uuid.uuid4(),
        "original_filename": "IMG_001.jpg",
        "ai_analysis": SimpleNamespace(
            caption="Students performing on stage.",
            primary_subject="dance group",
            scene_type="performance",
            event_context="college fest",
            tags=["dance", "stage"],
            suggested_primary_folder="Performances",
            suggested_sub_folder="Dance",
        ),
        "review_decision": None,
        "quality_signal": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_mock_embedding_provider_is_deterministic_and_normalized() -> None:
    provider = search_service.MockEmbeddingProvider(dimension=8)

    first = provider.embed_text("Stage Performance")
    second = provider.embed_text(" stage   performance ")

    assert first == second
    assert len(first) == 8
    assert round(sum(value * value for value in first), 6) == 1


def test_mock_embedding_provider_defaults_to_media_embedding_dimension() -> None:
    provider = search_service.MockEmbeddingProvider()

    assert provider.dimension == search_service.MEDIA_EMBEDDING_DIMENSION


def test_build_indexed_text_prefers_review_metadata() -> None:
    media = make_media(
        review_decision=SimpleNamespace(
            final_primary_folder="Highlights",
            final_sub_folder="Opening Dance",
            final_tags=["featured", "approved"],
            review_reasons=["low_confidence"],
            reviewer_note="Use this in recap.",
        ),
        quality_signal=SimpleNamespace(quality_label="sharp"),
    )

    indexed_text = search_service.build_indexed_text(media)

    assert "Students performing on stage." in indexed_text
    assert "Highlights" in indexed_text
    assert "Opening Dance" in indexed_text
    assert "featured" in indexed_text
    assert "low_confidence" in indexed_text
    assert "sharp" in indexed_text


def test_search_result_score_converts_distance_to_similarity() -> None:
    media = make_media()
    result = search_service.SearchResult(media=media, score=max(0.0, 1.0 - 0.25))

    assert result.score == 0.75


def test_search_filters_defaults_target_export_ready_media() -> None:
    filters = search_service.SearchFilters()

    assert filters.include_duplicates is False
    assert filters.include_blurry is True
    assert filters.include_pending is False
    assert filters.export_ready_only is True


def test_apply_search_filters_excludes_blurry_but_keeps_unknown_quality() -> None:
    event_id = uuid.uuid4()

    with _search_filter_session() as db:
        sharp_id = _insert_media_with_signals(
            db,
            event_id=event_id,
            quality_label="sharp",
            review_status="approved",
            include_in_export=True,
        )
        unknown_quality_id = _insert_media_with_signals(
            db,
            event_id=event_id,
            quality_label=None,
            review_status="approved",
            include_in_export=True,
        )
        _insert_media_with_signals(
            db,
            event_id=event_id,
            quality_label="blurry",
            review_status="approved",
            include_in_export=True,
        )
        db.commit()

        rows = db.execute(
            search_service.apply_search_filters(
                _base_media_filter_statement(event_id),
                search_service.SearchFilters(
                    include_blurry=False,
                    export_ready_only=True,
                ),
            )
        ).all()

    assert {row[0] for row in rows} == {sharp_id, unknown_quality_id}


def test_apply_search_filters_excludes_duplicates_and_pending_by_default() -> None:
    event_id = uuid.uuid4()

    with _search_filter_session() as db:
        ready_id = _insert_media_with_signals(
            db,
            event_id=event_id,
            quality_label="sharp",
            is_duplicate=False,
            review_status="approved",
            include_in_export=True,
        )
        _insert_media_with_signals(
            db,
            event_id=event_id,
            quality_label="sharp",
            is_duplicate=True,
            review_status="approved",
            include_in_export=True,
        )
        _insert_media_with_signals(
            db,
            event_id=event_id,
            quality_label="sharp",
            is_duplicate=False,
            review_status="pending",
            include_in_export=False,
        )
        db.commit()

        rows = db.execute(
            search_service.apply_search_filters(
                _base_media_filter_statement(event_id),
                search_service.SearchFilters(),
            )
        ).all()

    assert [row[0] for row in rows] == [ready_id]


def _search_filter_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "create table media_assets ("
                "id char(32) primary key, "
                "event_id char(32) not null, "
                "original_filename varchar(255) not null, "
                "created_at datetime"
                ")"
            )
        )
        connection.execute(
            text(
                "create table quality_signals ("
                "id char(32) primary key, "
                "media_id char(32) not null, "
                "quality_label varchar(40), "
                "is_duplicate boolean not null"
                ")"
            )
        )
        connection.execute(
            text(
                "create table review_decisions ("
                "id char(32) primary key, "
                "media_id char(32) not null, "
                "status varchar(40) not null, "
                "include_in_export boolean not null"
                ")"
            )
        )
    return Session()


def _base_media_filter_statement(event_id: uuid.UUID):
    return (
        select(MediaAsset.id)
        .select_from(MediaAsset)
        .outerjoin(MediaAsset.quality_signal)
        .outerjoin(MediaAsset.review_decision)
        .where(MediaAsset.event_id == event_id)
        .order_by(MediaAsset.original_filename.asc())
    )


def _insert_media_with_signals(
    db,
    event_id: uuid.UUID,
    quality_label: str | None,
    review_status: str,
    include_in_export: bool,
    is_duplicate: bool = False,
) -> uuid.UUID:
    media_id = uuid.uuid4()
    db.execute(
        text(
            "insert into media_assets (id, event_id, original_filename, created_at) "
            "values (:id, :event_id, :original_filename, CURRENT_TIMESTAMP)"
        ),
        {
            "id": media_id.hex,
            "event_id": event_id.hex,
            "original_filename": f"{media_id.hex}.jpg",
        },
    )
    db.execute(
        text(
            "insert into quality_signals (id, media_id, quality_label, is_duplicate) "
            "values (:id, :media_id, :quality_label, :is_duplicate)"
        ),
        {
            "id": uuid.uuid4().hex,
            "media_id": media_id.hex,
            "quality_label": quality_label,
            "is_duplicate": is_duplicate,
        },
    )
    db.execute(
        text(
            "insert into review_decisions (id, media_id, status, include_in_export) "
            "values (:id, :media_id, :status, :include_in_export)"
        ),
        {
            "id": uuid.uuid4().hex,
            "media_id": media_id.hex,
            "status": review_status,
            "include_in_export": include_in_export,
        },
    )
    return media_id

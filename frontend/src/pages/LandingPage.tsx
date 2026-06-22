import { HeroChaos } from '@/components/landing/HeroChaos'
import { WorkflowLayersPreview } from '@/components/landing/WorkflowLayersPreview'
import { ReviewFocusPreview } from '@/components/landing/ReviewFocusPreview'
import { SearchMomentPreview } from '@/components/landing/SearchMomentPreview'
import { ExportCompressionPreview } from '@/components/landing/ExportCompressionPreview'
import { FinalCTA } from '@/components/landing/FinalCTA'

export function LandingPage() {
  return (
    <main className="min-h-screen bg-background text-foreground selection:bg-primary/30">
      <HeroChaos />
      <WorkflowLayersPreview />
      <ReviewFocusPreview />
      <SearchMomentPreview />
      <ExportCompressionPreview />
      <FinalCTA />
    </main>
  )
}

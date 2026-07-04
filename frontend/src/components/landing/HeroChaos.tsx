import { useRef } from 'react'
import { ArrowRight, ChevronDown } from 'lucide-react'
import { Link } from 'react-router-dom'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useGSAP } from '@gsap/react'

gsap.registerPlugin(ScrollTrigger)

export function HeroChaos() {
  const containerRef = useRef<HTMLDivElement>(null)
  const wallWrapperRef = useRef<HTMLDivElement>(null)
  const wallInnerRef = useRef<HTMLDivElement>(null)
  const columnsRef = useRef<(HTMLDivElement | null)[]>([])
  const textRefs = useRef<(HTMLElement | null)[]>([])

  useGSAP(() => {
    let mm = gsap.matchMedia()

    // 1. Initial Load Animation
    mm.add("(prefers-reduced-motion: no-preference)", () => {
      const tl = gsap.timeline()

      // Subtle photo wall fade-in and scale
      tl.fromTo(wallWrapperRef.current,
        { opacity: 0, scale: 1.05 },
        { opacity: 1, scale: 1.1, duration: 2, ease: "power2.out" }
        , 0)

      // Clean, staggered entrance for text
      tl.fromTo(textRefs.current,
        { opacity: 0, y: 30 },
        { opacity: 1, y: 0, duration: 1.2, stagger: 0.15, ease: "power3.out" }
        , 0.4)
    })

    // 2. Desktop Parallax & Scroll Transition
    mm.add("(min-width: 768px) and (prefers-reduced-motion: no-preference)", () => {

      // Column parallax on scroll (chaos separating/drifting)
      columnsRef.current.forEach((col, i) => {
        if (!col) return
        gsap.to(col, {
          yPercent: i % 2 === 0 ? -15 : -30, // Drift upwards at different rates
          ease: "none",
          scrollTrigger: {
            trigger: containerRef.current,
            start: "top top",
            end: "bottom top",
            scrub: true
          }
        })
      })

      // Fade out the wall as we transition into the Layers section
      gsap.to(wallInnerRef.current, {
        opacity: 0,
        scrollTrigger: {
          trigger: containerRef.current,
          start: "center top", // Start fading halfway down the hero
          end: "bottom top",
          scrub: true
        }
      })

      // Subtle Mouse Parallax
      const xTo = gsap.quickTo(wallWrapperRef.current, "x", { duration: 0.8, ease: "power3" })
      const yTo = gsap.quickTo(wallWrapperRef.current, "y", { duration: 0.8, ease: "power3" })

      const onMouseMove = (e: MouseEvent) => {
        const centerX = window.innerWidth / 2
        const centerY = window.innerHeight / 2
        // Drift oppositely to mouse, kept very subtle
        xTo((centerX - e.clientX) * 0.02)
        yTo((centerY - e.clientY) * 0.02)
      }

      window.addEventListener("mousemove", onMouseMove)
      return () => {
        window.removeEventListener("mousemove", onMouseMove)
      }
    })

    // 3. Mobile fallback entrance
    mm.add("(max-width: 767px) or (prefers-reduced-motion: reduce)", () => {
      gsap.fromTo(wallWrapperRef.current, { opacity: 0 }, { opacity: 1, duration: 1 })
      gsap.fromTo(textRefs.current, { opacity: 0 }, { opacity: 1, duration: 1, stagger: 0.1 })
    })

    return () => mm.revert()
  }, { scope: containerRef })

  return (
    <section ref={containerRef} className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden bg-background">

      {/* Background Image Chaos */}
      <div ref={wallWrapperRef} className="absolute inset-0 pointer-events-none transform scale-110">
        <div ref={wallInnerRef} className="w-full h-full opacity-30 grid grid-cols-2 md:grid-cols-4 gap-4 p-4">

          {/* Column 1 */}
          <div ref={el => { columnsRef.current[0] = el }} className="flex flex-col gap-4">
            <img src="https://images.unsplash.com/photo-1540575467063-178a50c2df87?auto=format&fit=crop&q=80&w=800" className="w-full h-64 object-cover rounded-md shadow-2xl border border-border/20" alt="" />
            <img src="https://images.unsplash.com/photo-1511578314322-379afb476865?auto=format&fit=crop&q=80&w=800" className="w-full h-64 object-cover rounded-md shadow-2xl border border-border/20" alt="" />
          </div>

          {/* Column 2 */}
          <div ref={el => { columnsRef.current[1] = el }} className="flex flex-col gap-4 translate-y-12">
            <img src="https://images.unsplash.com/photo-1511795409834-ef04bbd61622?auto=format&fit=crop&q=80&w=800" className="w-full h-64 object-cover rounded-md shadow-2xl border border-border/20" alt="" />
            <img src="https://images.unsplash.com/photo-1591115765373-5207764f72e7?auto=format&fit=crop&q=80&w=800" className="w-full h-64 object-cover rounded-md shadow-2xl border border-border/20" alt="" />
          </div>

          {/* Column 3 */}
          <div ref={el => { columnsRef.current[2] = el }} className="flex flex-col gap-4">
            <img src="https://images.unsplash.com/photo-1504384308090-c894fdcc538d?auto=format&fit=crop&q=80&w=800" className="w-full h-64 object-cover rounded-md shadow-2xl border border-border/20" alt="" />
            <img src="https://images.unsplash.com/photo-1558008258-3256797b43f3?auto=format&fit=crop&q=80&w=800" className="w-full h-64 object-cover rounded-md shadow-2xl border border-border/20" alt="" />
          </div>

          {/* Column 4 */}
          <div ref={el => { columnsRef.current[3] = el }} className="flex flex-col gap-4 translate-y-12">
            <img src="https://images.unsplash.com/photo-1515169067868-5387ec356754?auto=format&fit=crop&q=80&w=800" className="w-full h-64 object-cover rounded-md shadow-2xl border border-border/20" alt="" />
            <img src="https://images.unsplash.com/photo-1505373877841-8d25f7d46678?auto=format&fit=crop&q=80&w=800" className="w-full h-64 object-cover rounded-md shadow-2xl border border-border/20" alt="" />
          </div>

        </div>
      </div>
      {/* Subtle overlay to guarantee text readability against moving images */}
      <div className="absolute inset-0 bg-background/60 pointer-events-none z-[1]" />

      <div className="relative z-10 flex flex-col items-center text-center max-w-4xl px-6">
        <div ref={el => { textRefs.current[0] = el }} className="mono-label text-primary mb-6">Sorty: The Intelligent Event Media Pipeline</div>
        <h1 ref={el => { textRefs.current[1] = el }} className="text-5xl md:text-7xl font-semibold tracking-tight text-foreground mb-8">
          Sorty Tames the Event Media Chaos.
        </h1>
        <p ref={el => { textRefs.current[2] = el }} className="text-lg md:text-xl text-muted-foreground max-w-2xl mb-10 leading-relaxed">
          Sorty is the professional workstation that turns thousands of raw event photos into reviewed, searchable, delivery-ready packs. Let Sorty handle the sorting so you can focus on the shooting.
        </p>

        <div ref={el => { textRefs.current[3] = el }} className="flex flex-col sm:flex-row items-center gap-4 mb-6">
          <a
            href="#workflow-layers"
            onClick={(e) => {
              e.preventDefault();
              document.getElementById('workflow-layers')?.scrollIntoView({ behavior: 'smooth' })
            }}
            className="group flex items-center gap-2 rounded-sm bg-primary px-8 py-4 text-base font-medium text-primary-foreground transition-all hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background w-full sm:w-auto justify-center"
          >
            Watch the Workflow
            <ChevronDown className="size-5 transition-transform" />
          </a>

          <Link
            to="/"
            className="group flex items-center gap-2 rounded-sm border border-border bg-transparent px-8 py-4 text-base font-medium text-foreground transition-all hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background w-full sm:w-auto justify-center"
          >
            Open Dashboard
            <ArrowRight className="size-5 transition-transform" />
          </Link>
        </div>

        <p ref={el => { textRefs.current[4] = el }} className="text-sm text-muted-foreground/60 font-medium">
          Sorty is engineered for high-volume event teams.
        </p>
      </div>

      {/* Fade out to black at bottom for smooth section transition */}
      <div className="absolute bottom-0 left-0 right-0 h-48 bg-gradient-to-t from-background to-transparent pointer-events-none z-10" />
    </section>
  )
}

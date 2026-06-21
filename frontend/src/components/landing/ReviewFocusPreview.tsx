import { useRef } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useGSAP } from '@gsap/react'

gsap.registerPlugin(ScrollTrigger)

export function ReviewFocusPreview() {
  const containerRef = useRef<HTMLDivElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)
  const cardRef = useRef<HTMLDivElement>(null)
  const imageRef = useRef<HTMLImageElement>(null)
  const focusLabelRef = useRef<HTMLDivElement>(null)
  const inspectorRef = useRef<HTMLDivElement>(null)
  const actionsRef = useRef<HTMLDivElement>(null)
  const thumbsRef = useRef<HTMLDivElement>(null)

  useGSAP(() => {
    let mm = gsap.matchMedia()

    mm.add("(min-width: 768px) and (prefers-reduced-motion: no-preference)", () => {
      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: containerRef.current,
          start: "top 65%", 
          toggleActions: "play none none reverse"
        }
      })

      // Initial Setup
      gsap.set(overlayRef.current, { opacity: 0 })
      gsap.set(cardRef.current, { opacity: 0, y: 40, rotationX: 10, transformPerspective: 1000 })
      gsap.set(imageRef.current, { filter: 'blur(8px) grayscale(100%)', opacity: 0.5 })
      gsap.set(focusLabelRef.current, { opacity: 1, scale: 1 })
      gsap.set(thumbsRef.current, { x: -20, opacity: 0 })
      
      if (inspectorRef.current) {
        gsap.set(inspectorRef.current.children, { opacity: 0, x: 10 })
      }
      if (actionsRef.current) {
        gsap.set(actionsRef.current.children, { opacity: 0, y: 10, scale: 0.9 })
      }

      // 1. Darken background gently
      tl.to(overlayRef.current, { opacity: 1, duration: 0.8, ease: "power2.inOut" })
      
      // 2. Card enters focus
      tl.to(cardRef.current, { opacity: 1, y: 0, rotationX: 0, duration: 1, ease: "power3.out" }, "-=0.6")

      // 3. Thumbnails slide in
      tl.to(thumbsRef.current, { x: 0, opacity: 1, duration: 0.6, ease: "power2.out" }, "-=0.6")

      // 4. Image sharpens (Isolating the issue)
      tl.to(imageRef.current, { filter: 'blur(0px) grayscale(0%)', opacity: 1, duration: 1, ease: "power2.inOut" }, "-=0.2")
      tl.to(focusLabelRef.current, { opacity: 0, scale: 0.9, duration: 0.5, ease: "power2.inOut" }, "<")

      // 5. Inspector details appear
      if (inspectorRef.current) {
        tl.to(inspectorRef.current.children, { opacity: 1, x: 0, duration: 0.6, stagger: 0.1, ease: "power2.out" }, "-=0.5")
      }

      // 6. Action buttons ready for human input
      if (actionsRef.current) {
        tl.to(actionsRef.current.children, { opacity: 1, y: 0, scale: 1, duration: 0.5, stagger: 0.1, ease: "back.out(1.5)" }, "-=0.3")
      }
    })

    // Mobile fallback / Reduced Motion
    mm.add("(max-width: 767px) or (prefers-reduced-motion: reduce)", () => {
      gsap.fromTo(cardRef.current, 
        { opacity: 0, y: 20 },
        { 
          opacity: 1, y: 0, duration: 1, 
          scrollTrigger: {
            trigger: cardRef.current,
            start: "top 85%",
            toggleActions: "play none none reverse"
          }
        }
      )
    })

    return () => mm.revert()
  }, { scope: containerRef })

  return (
    <section ref={containerRef} className="relative py-32 border-t border-border/10 overflow-hidden bg-background">
      {/* Background Darken Overlay */}
      <div ref={overlayRef} className="absolute inset-0 bg-black/60 pointer-events-none" />

      <div className="container mx-auto px-6 max-w-6xl relative z-10">
        <div className="grid md:grid-cols-2 gap-16 items-center">
          <div>
            <div className="mono-label text-primary mb-4">Human-in-the-Loop</div>
            <h2 className="text-3xl md:text-5xl font-semibold mb-6">Focus on the Edge Cases</h2>
            <p className="text-muted-foreground text-lg leading-relaxed mb-8">
              AI handles the 90%. But some moments are blurry, ambiguous, or highly sensitive. The Review Queue isolates only the uncertain images, letting you make swift, confident decisions without sifting through thousands of perfect shots.
            </p>
            <ul className="space-y-4">
              <li className="flex items-center gap-3 text-sm font-medium text-foreground">
                <div className="size-1.5 rounded-full bg-primary" />
                Blur detection threshold
              </li>
              <li className="flex items-center gap-3 text-sm font-medium text-foreground">
                <div className="size-1.5 rounded-full bg-primary" />
                Closed-eyes flagging
              </li>
              <li className="flex items-center gap-3 text-sm font-medium text-foreground">
                <div className="size-1.5 rounded-full bg-primary" />
                Rapid approve/reject hotkeys
              </li>
            </ul>
          </div>
          
          <div ref={cardRef} className="relative rounded-md border border-border/50 bg-surface flex flex-col shadow-[0_20px_60px_rgba(0,0,0,0.6)] overflow-hidden text-sm">
            {/* Mock Header */}
            <div className="flex h-10 items-center justify-between border-b border-border bg-card px-3">
              <span className="mono-label text-muted-foreground text-[10px]">Queue Progress: 14 items</span>
              <span className="rounded-full bg-warn/10 px-2 py-0.5 text-[10px] font-medium text-warn border border-warn/20">Review Required</span>
            </div>
            
            <div className="flex min-h-[300px]">
              {/* Mock Sidebar Thumbnails */}
              <div ref={thumbsRef} className="w-16 border-r border-border flex flex-col gap-2 p-2 bg-surface/50">
                <div className="aspect-square rounded border-2 border-primary overflow-hidden">
                  <img src="/events/speaker-portrait.png" className="w-full h-full object-cover" alt="" />
                </div>
                <div className="aspect-square rounded border border-border overflow-hidden opacity-50 grayscale hover:opacity-100 hover:grayscale-0 transition-all">
                  <img src="/events/hackathon.png" className="w-full h-full object-cover" alt="" />
                </div>
                <div className="aspect-square rounded border border-border overflow-hidden opacity-50 grayscale hover:opacity-100 hover:grayscale-0 transition-all">
                  <img src="/events/gala.png" className="w-full h-full object-cover" alt="" />
                </div>
              </div>

              {/* Mock Main Area */}
              <div className="flex-1 flex flex-col bg-background relative p-4">
                <div className="flex-1 relative rounded border border-border overflow-hidden flex items-center justify-center mb-4 bg-card">
                  <img ref={imageRef} src="/events/speaker-portrait.png" className="absolute inset-0 w-full h-full object-cover" alt="Preview" />
                  <div ref={focusLabelRef} className="z-10 bg-surface/90 px-3 py-1.5 rounded-sm border border-border text-xs backdrop-blur font-medium shadow-lg">Focus Issue Detected</div>
                </div>
                
                {/* Mock Actions */}
                <div ref={actionsRef} className="flex justify-center gap-4 border-t border-border/50 pt-3">
                  <div className="flex flex-col items-center gap-1 text-muted-foreground">
                    <div className="size-8 rounded-full border border-border bg-surface flex items-center justify-center hover:bg-muted hover:text-foreground transition-colors cursor-pointer">✕</div>
                  </div>
                  <div className="flex flex-col items-center gap-1">
                    <div className="size-10 rounded-full border border-ok/50 bg-ok/10 text-ok flex items-center justify-center hover:bg-ok/20 transition-colors cursor-pointer shadow-[0_0_15px_rgba(var(--color-ok),0.2)]">✓</div>
                  </div>
                  <div className="flex flex-col items-center gap-1 text-muted-foreground">
                    <div className="size-8 rounded-full border border-border bg-surface flex items-center justify-center hover:bg-muted hover:text-foreground transition-colors cursor-pointer">⚑</div>
                  </div>
                </div>
              </div>

              {/* Mock Inspector */}
              <div ref={inspectorRef} className="w-40 border-l border-border bg-card p-3 flex flex-col gap-4 text-xs">
                <div>
                  <div className="mono-label text-muted-foreground text-[10px] mb-1">Inspector</div>
                  <div className="font-medium text-foreground">Blur detected</div>
                </div>
                <div>
                  <div className="mono-label text-muted-foreground text-[10px] mb-1">Quality</div>
                  <div className="text-muted-foreground">Low</div>
                </div>
                <div>
                  <div className="mono-label text-muted-foreground text-[10px] mb-1">AI Confidence</div>
                  <div className="text-warn">62%</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

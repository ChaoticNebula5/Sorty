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

      // 4. Image highlights (Isolating the issue, keeping blur)
      tl.to(imageRef.current, { filter: 'blur(8px) grayscale(0%)', opacity: 0.9, duration: 1, ease: "power2.inOut" }, "-=0.2")
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
            <h2 className="text-3xl md:text-5xl font-semibold mb-6">Sorty's Review Queue Flags the Edge Cases</h2>
            <p className="text-muted-foreground text-lg leading-relaxed mb-8">
              Sorty automates the bulk of your sorting while keeping you in complete creative control. Sorty's intelligent review queue isolates only the blurry, ambiguous, or sensitive shots, letting you make swift decisions without sifting through perfect photos.
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
          
          <div ref={cardRef} className="relative rounded-md border border-border bg-card flex flex-col shadow-xl overflow-hidden text-sm">
            {/* Mock Header */}
            <div className="flex h-10 items-center justify-between border-b border-border bg-card px-3">
              <span className="mono-label text-muted-foreground text-[10px]">Queue Progress: 14 items</span>
              <span className="rounded-full bg-warn/10 px-2 py-0.5 text-[10px] font-medium text-warn border border-warn/20">Review Required</span>
            </div>
            
            <div className="flex min-h-[300px]">
              {/* Mock Sidebar Thumbnails */}
              <div ref={thumbsRef} className="w-16 border-r border-border flex flex-col gap-2 p-2 bg-surface">
                <button className="aspect-square rounded border-2 border-primary overflow-hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background">
                  <img src="https://images.unsplash.com/photo-1558008258-3256797b43f3?auto=format&fit=crop&q=80&w=800" className="w-full h-full object-cover" alt="" />
                </button>
                <button className="aspect-square rounded border border-border overflow-hidden opacity-50 grayscale hover:opacity-100 hover:grayscale-0 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background">
                  <img src="https://images.unsplash.com/photo-1504384308090-c894fdcc538d?auto=format&fit=crop&q=80&w=800" className="w-full h-full object-cover" alt="" />
                </button>
                <button className="aspect-square rounded border border-border overflow-hidden opacity-50 grayscale hover:opacity-100 hover:grayscale-0 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background">
                  <img src="https://images.unsplash.com/photo-1511795409834-ef04bbd61622?auto=format&fit=crop&q=80&w=800" className="w-full h-full object-cover" alt="" />
                </button>
              </div>

              {/* Mock Main Area */}
              <div className="flex-1 flex flex-col bg-background relative p-4">
                <div className="flex-1 relative rounded border border-border overflow-hidden flex items-center justify-center mb-4 bg-elevated">
                  <img ref={imageRef} src="https://images.unsplash.com/photo-1558008258-3256797b43f3?auto=format&fit=crop&q=80&w=800" className="absolute inset-0 w-full h-full object-cover scale-105" alt="Preview" />
                  <div ref={focusLabelRef} className="z-10 bg-card px-3 py-1.5 rounded-sm border border-border text-xs font-medium shadow-sm">Focus Issue Detected</div>
                </div>
                
                {/* Mock Actions */}
                <div ref={actionsRef} className="flex justify-center gap-4 border-t border-border/50 pt-3">
                  <div className="flex flex-col items-center gap-1 text-muted-foreground">
                    <button className="size-8 rounded-full border border-border bg-surface flex items-center justify-center hover:bg-muted hover:text-foreground transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background">✕</button>
                  </div>
                  <div className="flex flex-col items-center gap-1">
                    <button className="size-10 rounded-full border border-ok/50 bg-ok/10 text-ok flex items-center justify-center hover:bg-ok/20 transition-colors cursor-pointer shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ok focus-visible:ring-offset-2 focus-visible:ring-offset-background">✓</button>
                  </div>
                  <div className="flex flex-col items-center gap-1 text-muted-foreground">
                    <button className="size-8 rounded-full border border-border bg-surface flex items-center justify-center hover:bg-muted hover:text-foreground transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background">⚑</button>
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

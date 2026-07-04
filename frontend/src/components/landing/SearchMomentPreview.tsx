import { useRef } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { TextPlugin } from 'gsap/TextPlugin'
import { useGSAP } from '@gsap/react'

gsap.registerPlugin(ScrollTrigger, TextPlugin)

export function SearchMomentPreview() {
  const containerRef = useRef<HTMLDivElement>(null)
  const textRefs = useRef<(HTMLElement | null)[]>([])
  
  const searchBoxRef = useRef<HTMLDivElement>(null)
  const queryContainerRef = useRef<HTMLDivElement>(null)
  const cursorRef = useRef<HTMLDivElement>(null)
  const statusRef = useRef<HTMLDivElement>(null)
  
  const gridRef = useRef<HTMLDivElement>(null)
  const gridItemsRef = useRef<(HTMLDivElement | null)[]>([])
  const matchChipRef = useRef<HTMLDivElement>(null)

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
      gsap.set(textRefs.current, { opacity: 0, y: 30 })
      gsap.set(searchBoxRef.current, { opacity: 0, y: 20 })
      gsap.set(cursorRef.current, { opacity: 0 })
      gsap.set(statusRef.current, { opacity: 0 })
      
      // Grid items start hidden but full color
      gsap.set(gridItemsRef.current.filter(Boolean), { opacity: 0, y: 20, filter: 'grayscale(0%)' })
      gsap.set(matchChipRef.current, { opacity: 0, scale: 0.8 })

      // Cursor infinite blink (slower, more natural)
      gsap.to(cursorRef.current, { opacity: 1, duration: 0.5, repeat: -1, yoyo: true, ease: "steps(1)" })

      // 1. Text elements slide in
      tl.to(textRefs.current, { opacity: 1, y: 0, duration: 0.8, stagger: 0.15, ease: "power3.out" })

      // 2. Search box appears
      tl.to(searchBoxRef.current, { opacity: 1, y: 0, duration: 0.6, ease: "power2.out" }, "-=0.4")

      // 3. Query "types" out smoothly and linearly
      tl.addLabel("typingStart", "+=0.1")
      // Start with empty text, then let GSAP type it
      gsap.set(queryContainerRef.current, { text: "" })
      tl.to(queryContainerRef.current, { text: "speaker on stage under blue lights", duration: 2.0, ease: "none" }, "typingStart")
      
      // 4. Searching status appears AFTER typing finishes
      tl.addLabel("typingEnd", "typingStart+=2.0")
      tl.to(statusRef.current, { opacity: 1, duration: 0.3 }, "typingEnd")

      // 5. Grid tiles populate
      tl.to(gridItemsRef.current.filter(Boolean), { opacity: 1, y: 0, duration: 0.6, stagger: 0.1, ease: "power2.out" }, "typingEnd+=0.2")

      // 6. Give a small pause for the grid to finish loading, then resolve
      tl.addLabel("resolveStart", "typingEnd+=1.2")
      
      const nonMatches = gridItemsRef.current.slice(1).filter(Boolean)
      tl.to(nonMatches, { opacity: 0.4, filter: 'grayscale(100%)', duration: 0.8, ease: "power2.inOut" }, "resolveStart")
      
      // Slowly fade out "Searching..."
      tl.to(statusRef.current, { opacity: 0, duration: 0.4 }, "resolveStart")
      
      // 7. Best match highlighted smoothly
      if (gridItemsRef.current[0]) {
        tl.to(gridItemsRef.current[0], { scale: 1.02, duration: 0.6 }, "resolveStart+=0.2")
        tl.add(() => {
           gridItemsRef.current[0]?.classList.add('border-primary', 'shadow-[0_0_20px_rgba(var(--color-primary),0.15)]')
        }, "resolveStart+=0.2")
      }
      tl.to(matchChipRef.current, { opacity: 1, scale: 1, duration: 0.5, ease: "back.out(1.2)" }, "resolveStart+=0.4")
    })

    // Mobile fallback / Reduced Motion
    mm.add("(max-width: 767px) or (prefers-reduced-motion: reduce)", () => {
      gsap.set(queryContainerRef.current, { text: "speaker on stage under blue lights" })
      
      // Set final state for images
      const nonMatchesMob = gridItemsRef.current.slice(1).filter(Boolean)
      if (nonMatchesMob.length > 0) {
        gsap.set(nonMatchesMob, { opacity: 0.4, filter: 'grayscale(100%)' })
      }
      if (gridItemsRef.current[0]) {
        gridItemsRef.current[0].classList.add('border-primary', 'shadow-[0_0_20px_rgba(var(--color-primary),0.15)]')
      }
      gsap.set(matchChipRef.current, { opacity: 1, scale: 1 })

      const elements = [textRefs.current[0], textRefs.current[1], textRefs.current[2], searchBoxRef.current, gridRef.current].filter(Boolean)
      
      gsap.fromTo(elements, 
        { opacity: 0, y: 20 },
        { 
          opacity: 1, y: 0, duration: 0.8, stagger: 0.15,
          scrollTrigger: {
            trigger: containerRef.current,
            start: "top 85%",
            toggleActions: "play none none reverse"
          }
        }
      )
    })

    return () => mm.revert()
  }, { scope: containerRef })

  return (
    <section ref={containerRef} className="relative py-32 bg-background border-t border-border/10 overflow-hidden">
      <div className="container mx-auto px-6 max-w-6xl relative z-10">
        <div className="grid md:grid-cols-2 gap-16 items-center">
          
          <div className="order-2 md:order-1 relative aspect-square rounded-md border border-border/50 bg-surface overflow-hidden p-6 flex flex-col shadow-2xl">
            {/* Fake Search Input */}
            <div ref={searchBoxRef} className="relative mb-6 w-full bg-background border border-border rounded-sm px-4 py-3 flex items-center h-12 shadow-sm">
              <div ref={queryContainerRef} className="flex-shrink-0 text-foreground font-medium whitespace-nowrap overflow-hidden">
                {/* Text is injected here by GSAP TextPlugin */}
              </div>
              <div ref={cursorRef} className="w-[2px] h-5 bg-primary ml-1 shrink-0" />
              <div ref={statusRef} className="absolute right-3 top-3 mono-label text-muted-foreground">Searching...</div>
            </div>
            
            {/* Results Grid */}
            <div ref={gridRef} className="grid grid-cols-2 gap-4 flex-1">
              <div ref={el => { gridItemsRef.current[0] = el }} className="rounded border border-border overflow-hidden relative bg-card transition-colors">
                <img src="https://images.unsplash.com/photo-1558008258-3256797b43f3?auto=format&fit=crop&q=80&w=800" className="w-full h-full object-cover" alt="" />
                <div ref={matchChipRef} className="absolute top-2 left-2 bg-background/95 px-2 py-1 text-xs mono-label text-primary rounded-sm border border-primary/20 backdrop-blur shadow-md">Semantic Match</div>
              </div>
              {/* Non-matches */}
              <div ref={el => { gridItemsRef.current[1] = el }} className="rounded border border-border overflow-hidden bg-card">
                <img src="https://images.unsplash.com/photo-1515169067868-5387ec356754?auto=format&fit=crop&q=80&w=800" className="w-full h-full object-cover" alt="" />
              </div>
              <div ref={el => { gridItemsRef.current[2] = el }} className="rounded border border-border overflow-hidden bg-card">
                <img src="https://images.unsplash.com/photo-1504384308090-c894fdcc538d?auto=format&fit=crop&q=80&w=800" className="w-full h-full object-cover" alt="" />
              </div>
              <div ref={el => { gridItemsRef.current[3] = el }} className="rounded border border-border overflow-hidden bg-card">
                <img src="https://images.unsplash.com/photo-1511578314322-379afb476865?auto=format&fit=crop&q=80&w=800" className="w-full h-full object-cover" alt="" />
              </div>
            </div>
          </div>
          
          <div className="order-1 md:order-2">
            <div ref={el => { textRefs.current[0] = el }} className="mono-label text-primary mb-4">Semantic Discovery</div>
            <h2 ref={el => { textRefs.current[1] = el }} className="text-3xl md:text-5xl font-semibold mb-6">Sorty's Instant Semantic Discovery</h2>
            <p ref={el => { textRefs.current[2] = el }} className="text-muted-foreground text-lg leading-relaxed mb-8">
              Find the exact moment instantly with Sorty. Sorty analyzes the semantic content of every image during ingestion, allowing your team to search by what happened (not by where a file is saved) using simple natural language.
            </p>
          </div>
          
        </div>
      </div>
    </section>
  )
}

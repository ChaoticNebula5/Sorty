import { useRef } from 'react'
import { FileArchive, Folder, FileText } from 'lucide-react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useGSAP } from '@gsap/react'

gsap.registerPlugin(ScrollTrigger)

export function ExportCompressionPreview() {
  const containerRef = useRef<HTMLDivElement>(null)
  const textRefs = useRef<(HTMLElement | null)[]>([])
  
  const centerAreaRef = useRef<HTMLDivElement>(null)
  const tilesRef = useRef<(HTMLDivElement | null)[]>([])
  const labelsRef = useRef<(HTMLDivElement | null)[]>([])
  const zipObjectRef = useRef<HTMLDivElement>(null)
  const statusChipRef = useRef<HTMLDivElement>(null)

  useGSAP(() => {
    let mm = gsap.matchMedia()

    mm.add("(min-width: 768px) and (prefers-reduced-motion: no-preference)", () => {
      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: containerRef.current,
          start: "top 60%",
          toggleActions: "play none none reverse"
        }
      })

      // Initial state
      gsap.set(textRefs.current, { opacity: 0, y: 30 })
      gsap.set(tilesRef.current, { 
        opacity: 0, 
        scale: 0, 
        x: (i) => [220, -240, 180, -200, 100, -110][i], 
        y: (i) => [-140, -100, 200, 160, -210, 120][i], 
        rotation: (i) => [-15, 20, 10, -25, 5, -10][i] 
      })
      gsap.set(labelsRef.current, { opacity: 0, y: 15, scale: 0.9 })
      gsap.set(zipObjectRef.current, { opacity: 0, scale: 0.5 })
      gsap.set(statusChipRef.current, { opacity: 0, y: 10, scale: 0.8 })

      // 1. Text elements slide in
      tl.to(textRefs.current, { opacity: 1, y: 0, duration: 0.8, stagger: 0.15, ease: "power3.out" })

      // 2. Small media tiles appear scattered
      tl.to(tilesRef.current, { opacity: 1, scale: 1, duration: 0.6, stagger: 0.08, ease: "back.out(1.5)" }, "-=0.4")

      // 3. Folder/file labels appear in order
      tl.to(labelsRef.current, { opacity: 1, y: 0, scale: 1, duration: 0.5, stagger: 0.15, ease: "power2.out" }, "-=0.2")

      // 4. Tiles and labels move inward toward the center (collapse)
      tl.addLabel("collapse", "+=0.4")
      tl.to(tilesRef.current, { x: 0, y: 0, rotation: 0, scale: 0.3, opacity: 0, duration: 0.8, ease: "power3.inOut" }, "collapse")
      tl.to(labelsRef.current, { x: 0, y: 0, scale: 0.5, opacity: 0, duration: 0.7, ease: "power3.inOut" }, "collapse+=0.1")

      // 5. ZIP object scales into focus instantly as they collapse
      tl.to(zipObjectRef.current, { opacity: 1, scale: 1, duration: 0.8, ease: "back.out(1.2)" }, "collapse+=0.4")

      // 6. "Ready for delivery" status chip appears
      tl.to(statusChipRef.current, { opacity: 1, y: 0, scale: 1, duration: 0.5, ease: "back.out(1.5)" }, "-=0.2")
    })

    // Mobile fallback / Reduced Motion
    mm.add("(max-width: 767px) or (prefers-reduced-motion: reduce)", () => {
      // Just show the final ZIP state and hide the intermediate animation parts
      gsap.set(tilesRef.current, { display: 'none' })
      gsap.set(labelsRef.current, { display: 'none' })
      gsap.set(statusChipRef.current, { opacity: 1, scale: 1 })
      
      const elements = [...textRefs.current, zipObjectRef.current]
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

  const mockImages = [
    '/events/dev-conference.png',
    '/events/gala.png',
    '/events/hackathon.png',
    '/events/networking.png',
    '/events/panel.png',
    '/events/speaker-portrait.png',
  ]

  const folderLabels = [
    { text: '/Keynote', icon: Folder },
    { text: '/Gala', icon: Folder },
    { text: 'metadata.csv', icon: FileText },
    { text: 'summary.md', icon: FileText }
  ]

  return (
    <section ref={containerRef} className="relative py-32 bg-background border-t border-border/10 overflow-hidden flex flex-col items-center">
      <div className="container mx-auto px-6 max-w-5xl text-center relative z-10">
        
        <div ref={el => { textRefs.current[0] = el }} className="mono-label text-primary mb-4">Export & Delivery</div>
        <h2 ref={el => { textRefs.current[1] = el }} className="text-3xl md:text-5xl font-semibold mb-6">Deliver the pack before the buzz fades.</h2>
        <p ref={el => { textRefs.current[2] = el }} className="text-muted-foreground text-lg leading-relaxed mb-16 max-w-2xl mx-auto">
          Reviewed media, metadata, and summary notes are compiled into one organized ZIP — ready for handoff.
        </p>

        <div ref={centerAreaRef} className="relative h-[400px] w-full max-w-2xl mx-auto flex items-center justify-center mb-16">
          
          {/* Scattered Tiles (Absolute) */}
          {mockImages.map((src, i) => (
            <div 
              key={`tile-${i}`} 
              ref={el => { tilesRef.current[i] = el }} 
              className="absolute size-24 md:size-32 rounded-md shadow-[0_15px_40px_rgba(0,0,0,0.5)] border border-border/50 overflow-hidden bg-surface flex items-center justify-center z-10"
            >
              <img src={src} className="w-full h-full object-cover opacity-80" alt="" />
            </div>
          ))}

          {/* Folder/File Labels (Absolute, slightly offset around center) */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-20">
            <div className="relative w-full h-full max-w-md">
              {folderLabels.map((item, i) => {
                const Icon = item.icon
                const positions = [
                  'top-[10%] left-[15%]',
                  'bottom-[15%] right-[10%]',
                  'top-[20%] right-[15%]',
                  'bottom-[25%] left-[5%]'
                ]
                return (
                  <div 
                    key={`label-${i}`} 
                    ref={el => { labelsRef.current[i] = el }}
                    className={`absolute ${positions[i]} flex items-center gap-2 bg-card/90 backdrop-blur border border-border px-4 py-2 rounded-md shadow-xl`}
                  >
                    <Icon className="size-4 text-primary" />
                    <span className="text-sm font-medium text-foreground">{item.text}</span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Final ZIP Object */}
          <div ref={zipObjectRef} className="relative z-30 w-72 aspect-square rounded-full border border-border/50 bg-surface flex flex-col items-center justify-center shadow-[0_30px_80px_rgba(0,0,0,0.7)] overflow-hidden group">
            <div className="absolute inset-0 bg-primary/5 transition-colors group-hover:bg-primary/10" />
            <FileArchive className="size-16 text-primary mb-4 transition-transform group-hover:scale-110 duration-500" />
            <div className="font-semibold text-xl text-foreground">Export_Pack.zip</div>
            <div className="mono-label text-muted-foreground mt-2">1,204 Files • 4.2 GB</div>
            
            <div ref={statusChipRef} className="absolute bottom-8 bg-ok/10 text-ok border border-ok/20 px-3 py-1 rounded-full text-[10px] font-bold tracking-wider shadow-[0_0_15px_rgba(var(--color-ok),0.2)]">
              READY FOR DELIVERY
            </div>
          </div>
          
        </div>

      </div>
    </section>
  )
}

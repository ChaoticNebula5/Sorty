import { useRef } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useGSAP } from '@gsap/react'
import { UploadCloud, Cpu, Eye, Search, Archive } from 'lucide-react'

gsap.registerPlugin(ScrollTrigger)

const layersData = [
  { id: 'Upload', desc: 'Ingest raw batch folders at high velocity.', chip: 'Processing', tone: 'info', icon: UploadCloud },
  { id: 'Analyze', desc: 'Semantic tagging, blur detection, face grouping.', chip: 'AI Active', tone: 'primary', icon: Cpu },
  { id: 'Review', desc: 'Human-in-the-loop curation for uncertain shots.', chip: '14 Pending', tone: 'warn', icon: Eye },
  { id: 'Search', desc: 'Find exact moments using natural language.', chip: 'Indexed', tone: 'ok', icon: Search },
  { id: 'Export', desc: 'Compile curated packs into organized ZIPs.', chip: 'Ready', tone: 'foreground', icon: Archive },
]

const getToneClasses = (tone: string) => {
  switch(tone) {
    case 'info': return 'bg-info/10 text-info border-info/20'
    case 'primary': return 'bg-primary/10 text-primary border-primary/20'
    case 'warn': return 'bg-warn/10 text-warn border-warn/20'
    case 'ok': return 'bg-ok/10 text-ok border-ok/20'
    case 'foreground': return 'bg-foreground/10 text-foreground border-foreground/20'
    default: return 'bg-muted/10 text-muted-foreground border-border'
  }
}

export function WorkflowLayersPreview() {
  const containerRef = useRef<HTMLDivElement>(null)
  const titleRef = useRef<HTMLDivElement>(null)
  const layersRef = useRef<(HTMLDivElement | null)[]>([])
  const progressLineRef = useRef<HTMLDivElement>(null)

  useGSAP(() => {
    let mm = gsap.matchMedia()

    mm.add("(min-width: 768px) and (prefers-reduced-motion: no-preference)", () => {
      gsap.set(layersRef.current, {
        xPercent: -50,
        yPercent: -50,
        y: (i) => i * 40,
        z: (i) => i * -100,
        rotationX: 25,
        opacity: (i) => 1 - (i * 0.15)
      })

      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: containerRef.current,
          start: "top top",
          end: "+=2000",
          scrub: 1,
          pin: true,
          anticipatePin: 1,
          onUpdate: (self) => {
            const activeIdx = Math.min(4, Math.max(0, Math.floor(self.progress * 5)))
            
            layersRef.current.forEach((layer, i) => {
              if (!layer) return
              
              if (i === activeIdx) {
                layer.classList.add('border-primary', 'shadow-[0_0_30px_rgba(var(--color-primary),0.15)]')
                layer.classList.remove('border-border/50', 'shadow-[0_15px_50px_rgba(0,0,0,0.5)]')
                layer.setAttribute('data-active', 'true')
              } else {
                layer.classList.remove('border-primary', 'shadow-[0_0_30px_rgba(var(--color-primary),0.15)]')
                layer.classList.add('border-border/50', 'shadow-[0_15px_50px_rgba(0,0,0,0.5)]')
                layer.setAttribute('data-active', 'false')
              }
            })
          }
        }
      })

      tl.to(titleRef.current, { opacity: 0, y: -20, duration: 0.5 }, 0)

      if (progressLineRef.current) {
        tl.to(progressLineRef.current, { scaleY: 1, ease: "none", duration: 2 }, 0)
      }

      tl.to(layersRef.current, {
        y: (i) => (i - 2) * 140, 
        z: 0,
        rotationX: 0,
        scale: 0.9,
        opacity: 1,
        duration: 2,
        ease: "power2.inOut",
        stagger: 0.1
      }, 0)
    })

    mm.add("(max-width: 767px) or (prefers-reduced-motion: reduce)", () => {
      layersRef.current.forEach((layer) => {
        gsap.fromTo(layer, 
          { opacity: 0, y: 20 },
          { 
            opacity: 1, 
            y: 0,
            scrollTrigger: {
              trigger: layer,
              start: "top 85%",
              toggleActions: "play none none reverse"
            }
          }
        )
      })
    })

    return () => mm.revert()
  }, { scope: containerRef })

  return (
    <section id="workflow-layers" ref={containerRef} className="relative bg-background border-t border-border/10">
      <div className="w-full h-full min-h-screen px-6 py-24 md:py-0 md:[perspective:1000px] flex flex-col md:block">
        
        <div className="absolute left-8 top-1/4 bottom-1/4 w-[2px] bg-surface hidden md:block z-0 rounded-full overflow-hidden">
          <div ref={progressLineRef} className="w-full h-full bg-primary origin-top" style={{ transform: 'scaleY(0)' }} />
        </div>

        <div ref={titleRef} className="mb-16 md:absolute md:top-24 md:left-1/2 md:-translate-x-1/2 md:text-center w-full z-0">
          <div className="mono-label text-primary mb-4">Decomposition</div>
          <h2 className="text-3xl md:text-5xl font-semibold">Sorty's Pipeline gives you Layers of Control</h2>
          <p className="mt-4 text-muted-foreground max-w-xl text-lg md:mx-auto">
            Sorty transforms a chaotic folder into a streamlined asset pipeline. Sorty separates ingestion, semantic analysis, and curation into distinct, manageable workflows that put you in control.
          </p>
        </div>

        <div className="relative flex-1 flex flex-col md:block w-full max-w-2xl mx-auto md:max-w-none md:h-screen z-10 [perspective:1000px]">
          {layersData.map((layer, i) => (
            <div 
              key={layer.id}
              ref={el => { layersRef.current[i] = el }}
              className="md:absolute md:top-1/2 md:left-1/2 relative w-full max-w-2xl bg-card border border-border/50 rounded-md shadow-[0_15px_50px_rgba(0,0,0,0.5)] overflow-hidden flex flex-col sm:flex-row mb-6 md:mb-0 transition-colors duration-300 group"
              data-active="false"
            >
              {/* Abstract Icon Graphic */}
              <div className="h-32 sm:h-auto sm:w-1/3 relative border-b sm:border-b-0 sm:border-r border-border overflow-hidden bg-surface flex items-center justify-center">
                 <div className="absolute inset-0 bg-primary/20 opacity-0 group-data-[active=true]:opacity-100 transition-opacity duration-700 blur-2xl rounded-full scale-150" />
                 <layer.icon className="w-16 h-16 opacity-30 text-muted-foreground group-data-[active=true]:text-primary group-data-[active=true]:opacity-100 transition-all duration-500 z-10 drop-shadow-md group-data-[active=true]:scale-110" />
                 <div className="absolute inset-0 bg-gradient-to-t sm:bg-gradient-to-r from-card to-transparent pointer-events-none z-20" />
              </div>
              
              {/* Content */}
              <div className="flex-1 p-4 md:p-5 flex flex-col justify-center bg-card">
                 <div className="flex justify-between items-start mb-2">
                    <div className="flex items-center gap-3">
                       <span className="mono-label text-muted-foreground opacity-50 transition-colors group-data-[active=true]:text-primary group-data-[active=true]:opacity-100">0{i+1}</span>
                       <span className="text-2xl font-semibold tracking-tight transition-colors text-muted-foreground group-data-[active=true]:text-foreground">{layer.id}</span>
                    </div>
                    <div className={`mono-label px-2 py-0.5 rounded-sm border transition-opacity opacity-50 group-data-[active=true]:opacity-100 ${getToneClasses(layer.tone)}`}>
                       {layer.chip}
                    </div>
                 </div>
                 <p className="text-muted-foreground text-sm leading-relaxed transition-colors group-data-[active=true]:text-foreground/90">{layer.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

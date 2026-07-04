import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'

export function FinalCTA() {
  return (
    <section className="relative py-32 bg-background border-t border-border/10 overflow-hidden">
      {/* Subtle background glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] bg-primary/5 blur-[100px] rounded-full pointer-events-none" />
      
      <div className="container relative z-10 mx-auto px-6 max-w-4xl text-center">
        <h2 className="text-4xl md:text-6xl font-semibold mb-8">
          Ready to let Sorty sort it out?
        </h2>
        <p className="text-xl text-muted-foreground mb-12">
          Experience Sorty, the professional event media workstation built to accelerate your delivery.
        </p>
        <Link 
          to="/" 
          className="inline-flex items-center gap-2 rounded-sm bg-primary px-8 py-4 text-base font-medium text-primary-foreground transition-all hover:bg-primary/90 hover:scale-105"
        >
          Open Dashboard
          <ArrowRight className="size-5 transition-transform group-hover:translate-x-1" />
        </Link>
      </div>
    </section>
  )
}

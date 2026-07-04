import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'

export function FinalCTA() {
  return (
    <section className="relative py-32 bg-background border-t border-border/10 overflow-hidden">
      <div className="container relative z-10 mx-auto px-6 max-w-4xl text-center">
        <h2 className="text-4xl md:text-6xl font-semibold mb-8">
          Ready to let Sorty sort it out?
        </h2>
        <p className="text-xl text-muted-foreground mb-12">
          Experience Sorty, the professional event media workstation built to accelerate your delivery.
        </p>
        <Link 
          to="/" 
          className="inline-flex items-center gap-2 rounded-sm bg-primary px-8 py-4 text-base font-medium text-primary-foreground transition-all hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          Open Dashboard
          <ArrowRight className="size-5 transition-transform" />
        </Link>
      </div>
    </section>
  )
}

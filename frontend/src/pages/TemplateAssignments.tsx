import { EpgSubNav } from "@/components/EpgSubNav"
import { TemplateAssignmentManager } from "@/components/TemplateAssignmentModal"
import { useSubscription } from "@/hooks/useSubscription"

/**
 * Template Assignments — assign event templates by sport or league.
 * Promoted from a modal to a static EPG page in the v2.7.0 IA overhaul.
 */
export function TemplateAssignments() {
  const { data: subscription } = useSubscription()
  const subscribedLeagues = subscription?.leagues ?? []

  return (
    <div className="space-y-2">
      <EpgSubNav />
      <div>
        <h1 className="text-xl font-bold">Template Assignments</h1>
        <p className="text-sm text-muted-foreground">
          Assign event templates by sport or league. More specific matches win: league &gt; sport &gt; default.
        </p>
      </div>
      <div className="pt-2">
        <TemplateAssignmentManager subscribedLeagues={subscribedLeagues} />
      </div>
    </div>
  )
}

import { useMemo } from "react"
import { AlertTriangle } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { validateTemplate } from "@/utils/templateValidation"
import type { TemplateFieldProps } from "./types"

// Default resolver that just returns the template unchanged
const defaultResolver = (template: string) => template

export function TemplateField({
  id,
  label,
  value,
  onChange,
  placeholder,
  helpText,
  fieldRefs,
  setLastFocusedField,
  multiline = false,
  resolveTemplate = defaultResolver,
  validationData,
  isEventTemplate = false,
}: TemplateFieldProps) {
  const preview = resolveTemplate(value)

  // Compute validation warnings
  const warnings = useMemo(() => {
    if (!validationData || !value) return []
    return validateTemplate(
      value,
      validationData.validNames,
      validationData.baseNames,
      isEventTemplate
    )
  }, [value, validationData, isEventTemplate])

  const hasWarnings = warnings.length > 0

  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      {multiline ? (
        <Textarea
          id={id}
          ref={(el) => {
            if (fieldRefs) fieldRefs.current[id] = el
          }}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setLastFocusedField?.(id)}
          placeholder={placeholder}
          className={`font-mono text-sm min-h-[80px] ${hasWarnings ? "border-amber-500/50 focus:border-amber-500" : ""}`}
        />
      ) : (
        <Input
          id={id}
          ref={(el) => {
            if (fieldRefs) fieldRefs.current[id] = el
          }}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setLastFocusedField?.(id)}
          placeholder={placeholder}
          className={`font-mono text-sm ${hasWarnings ? "border-amber-500/50 focus:border-amber-500" : ""}`}
        />
      )}
      {/* Validation Warnings */}
      {hasWarnings && (
        <div className="mt-1 px-2 py-1.5 bg-amber-500/10 border border-amber-500/30 rounded-sm">
          <div className="flex items-start gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-500 flex-shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              {warnings.map((w, i) => (
                <p key={i} className="text-xs text-amber-400">
                  {w.message}
                </p>
              ))}
            </div>
          </div>
        </div>
      )}
      {value && (
        <div className="mt-1 px-2 py-1 bg-secondary/50 border-l-2 border-primary rounded-sm">
          <span className="text-[10px] text-muted-foreground uppercase font-semibold mr-2">Preview:</span>
          <span className="text-sm italic">{preview || "(empty)"}</span>
        </div>
      )}
      {helpText && <p className="text-xs text-muted-foreground">{helpText}</p>}
    </div>
  )
}

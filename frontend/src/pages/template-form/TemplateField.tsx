import { useMemo, useState } from "react"
import { AlertTriangle, ImageOff, Loader2 } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { validateTemplate } from "@/utils/templateValidation"
import type { TemplateFieldProps } from "./types"

// Default resolver that just returns the template unchanged
const defaultResolver = (template: string) => template

/**
 * Live preview of an art/gamethumb URL — actually fetches and renders the image
 * so the user can confirm the resolved link works, with explicit loading and
 * broken-link states (a 200-shaped string preview alone can't prove that).
 * Keyed by url at the call site so it remounts fresh whenever the URL changes.
 */
function ImagePreview({ url }: { url: string }) {
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading")
  return (
    <div className="mt-1">
      {status === "error" ? (
        <div className="flex items-center gap-1.5 text-xs text-amber-500">
          <ImageOff className="h-3.5 w-3.5" />
          Image didn't load — check the URL resolves
        </div>
      ) : (
        <div className="relative inline-block">
          {status === "loading" && (
            <Loader2 className="absolute left-2 top-2 h-3.5 w-3.5 animate-spin text-muted-foreground" />
          )}
          <img
            src={url}
            alt="Art preview"
            onLoad={() => setStatus("ok")}
            onError={() => setStatus("error")}
            className="h-24 max-w-[12rem] rounded border border-border bg-muted/30 object-contain"
          />
        </div>
      )}
    </div>
  )
}

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
  isImageField = false,
}: TemplateFieldProps) {
  const preview = resolveTemplate(value)
  // Only render a live image when the resolved value is an absolute URL.
  // (Relative paths become absolute once an art base URL is configured — z02s.)
  const showImage = isImageField && /^https?:\/\//i.test(preview)

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
          <span className="text-sm italic break-all">{preview || "(empty)"}</span>
        </div>
      )}
      {showImage && <ImagePreview key={preview} url={preview} />}
      {helpText && <p className="text-xs text-muted-foreground">{helpText}</p>}
    </div>
  )
}

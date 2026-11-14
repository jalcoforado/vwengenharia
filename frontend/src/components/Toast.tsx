import { CheckCircle2, AlertTriangle, Info, X } from "lucide-react";

export type ToastTone = "success" | "warning" | "info";

export default function Toast({
  message,
  tone = "info",
  onClose,
}: {
  message: string;
  tone?: ToastTone;
  onClose: () => void;
}) {
  const Icon = tone === "success" ? CheckCircle2 : tone === "warning" ? AlertTriangle : Info;
  return (
    <div className={"toast toast-" + tone} role="status" aria-live="polite">
      <Icon size={18} />
      <span>{message}</span>
      <button className="toast-close" onClick={onClose} aria-label="Fechar mensagem">
        <X size={16} />
      </button>
    </div>
  );
}

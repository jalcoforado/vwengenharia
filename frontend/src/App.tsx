import { useEffect, useState } from "react";
import { CloudOff, RefreshCw, Smartphone, Wifi } from "lucide-react";

import { fieldDb } from "./offline/db";

export default function App() {
  const [online, setOnline] = useState(navigator.onLine);
  const [pending, setPending] = useState(0);

  useEffect(() => {
    const updateConnection = () => setOnline(navigator.onLine);
    const refreshPending = () => {
      void fieldDb.outbox.count().then(setPending);
    };

    window.addEventListener("online", updateConnection);
    window.addEventListener("offline", updateConnection);
    refreshPending();

    const timer = window.setInterval(refreshPending, 2000);
    return () => {
      window.removeEventListener("online", updateConnection);
      window.removeEventListener("offline", updateConnection);
      window.clearInterval(timer);
    };
  }, []);

  return (
    <main
      style={{
        fontFamily: "Inter, system-ui, sans-serif",
        maxWidth: 720,
        margin: "0 auto",
        padding: 24,
        color: "#111827",
      }}
    >
      <header style={{ marginBottom: 28 }}>
        <small style={{ fontWeight: 700, letterSpacing: 1.2 }}>VW ENGENHARIA</small>
        <h1 style={{ margin: "8px 0" }}>Operação de campo</h1>
        <p style={{ margin: 0, color: "#4b5563" }}>
          Agenda, checklist e medições preparadas para uso mesmo sem conexão.
        </p>
      </header>

      <section
        style={{
          display: "grid",
          gap: 12,
          gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
        }}
      >
        <article
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: 16,
            padding: 18,
          }}
        >
          {online ? <Wifi size={24} /> : <CloudOff size={24} />}
          <h2 style={{ fontSize: 18 }}>Conexão</h2>
          <strong>{online ? "Online" : "Offline"}</strong>
          <p style={{ color: "#6b7280", marginBottom: 0 }}>
            {online
              ? "O dispositivo pode sincronizar com o servidor."
              : "Continue trabalhando; as ações ficam na fila local."}
          </p>
        </article>

        <article
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: 16,
            padding: 18,
          }}
        >
          <RefreshCw size={24} />
          <h2 style={{ fontSize: 18 }}>Sincronização</h2>
          <strong>{pending} ação(ões) pendente(s)</strong>
          <p style={{ color: "#6b7280", marginBottom: 0 }}>
            Cada comando possui um identificador único para impedir duplicação.
          </p>
        </article>

        <article
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: 16,
            padding: 18,
          }}
        >
          <Smartphone size={24} />
          <h2 style={{ fontSize: 18 }}>PWA</h2>
          <strong>Pronto para instalação</strong>
          <p style={{ color: "#6b7280", marginBottom: 0 }}>
            A base local armazena agenda, checklists, rascunhos e outbox.
          </p>
        </article>
      </section>
    </main>
  );
}

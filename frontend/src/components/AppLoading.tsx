export default function AppLoading() {
  return (
    <div className="app-shell loading-shell" aria-busy="true" aria-label="Carregando aplicacao">
      <header className="topbar">
        <div>
          <span className="brand-kicker">MW Engenharia</span>
          <strong>Preparando operacao</strong>
        </div>
      </header>
      <main className="content">
        <section className="loading-heading">
          <div className="skeleton skeleton-kicker" />
          <div className="skeleton skeleton-title" />
          <div className="skeleton skeleton-copy" />
        </section>
        <section className="metric-grid">
          {[0, 1, 2, 3].map((item) => (
            <div className="metric-card loading-card" key={item}>
              <div className="skeleton skeleton-icon" />
              <div className="skeleton skeleton-number" />
              <div className="skeleton skeleton-label" />
            </div>
          ))}
        </section>
        <section className="section-card loading-list">
          <div className="skeleton skeleton-section-title" />
          {[0, 1, 2].map((item) => (
            <div className="loading-row" key={item}>
              <div className="skeleton skeleton-row-time" />
              <div>
                <div className="skeleton skeleton-row-title" />
                <div className="skeleton skeleton-row-copy" />
              </div>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}

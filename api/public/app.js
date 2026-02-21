const { useEffect, useMemo, useRef, useState } = React;

const SpotlightCard = ({
  children,
  className = "",
  spotlightColor = "rgba(42, 92, 255, 0.2)"
}) => {
  const divRef = useRef(null);
  const [isFocused, setIsFocused] = useState(false);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [opacity, setOpacity] = useState(0);

  const handleMouseMove = (event) => {
    if (!divRef.current || isFocused) return;

    const rect = divRef.current.getBoundingClientRect();
    setPosition({
      x: event.clientX - rect.left,
      y: event.clientY - rect.top
    });
  };

  const handleFocus = () => {
    setIsFocused(true);
    setOpacity(0.6);
  };

  const handleBlur = () => {
    setIsFocused(false);
    setOpacity(0);
  };

  const handleMouseEnter = () => {
    setOpacity(0.6);
  };

  const handleMouseLeave = () => {
    setOpacity(0);
  };

  return (
    <div
      ref={divRef}
      onMouseMove={handleMouseMove}
      onFocus={handleFocus}
      onBlur={handleBlur}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`card ${className}`}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity,
          pointerEvents: "none",
          transition: "opacity 500ms ease-in-out",
          background: `radial-gradient(circle at ${position.x}px ${position.y}px, ${spotlightColor}, transparent 80%)`
        }}
      />
      <div style={{ position: "relative", zIndex: 1 }}>{children}</div>
    </div>
  );
};

const formatTimestamp = (value) => {
  if (!value) return "Unknown";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(parsed);
};

const App = () => {
  const [latest, setLatest] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [latestResponse, historyResponse] = await Promise.all([
          fetch("/latest"),
          fetch("/history")
        ]);

        if (latestResponse.ok) {
          const latestPayload = await latestResponse.json();
          setLatest(latestPayload);
        }

        if (historyResponse.ok) {
          const historyPayload = await historyResponse.json();
          setHistory(Array.isArray(historyPayload) ? historyPayload : []);
        }
      } catch (err) {
        setError("Unable to load readings right now.");
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  const sortedHistory = useMemo(() => {
    return [...history].sort((a, b) =>
      String(b.timestamp).localeCompare(String(a.timestamp))
    );
  }, [history]);

  return (
    <div>
      <header className="hero reveal">
        <span className="badge">BVK smart meter</span>
        <h1>Water usage, at a glance.</h1>
        <p>
          Live snapshot of the latest meter reading, with a timeline of recent
          measurements pulled directly from the BVK integration.
        </p>
      </header>

      <div className="grid">
        <SpotlightCard
          className="reveal"
          spotlightColor="rgba(42, 92, 255, 0.18)"
        >
          <div className="section-title">
            <span>Current reading</span>
          </div>
          {loading ? (
            <p className="loading">Loading latest reading...</p>
          ) : latest ? (
            <>
              <div className="reading-value">{latest.reading} m3</div>
              <div className="reading-meta">
                Updated {formatTimestamp(latest.timestamp)}
              </div>
            </>
          ) : (
            <div className="reading-meta">No reading available yet.</div>
          )}
          {error ? <p className="error">{error}</p> : null}
        </SpotlightCard>

        <div className="card reveal">
          <div className="section-title">
            <span>History</span>
            <span>{sortedHistory.length} entries</span>
          </div>
          {loading ? (
            <p className="loading">Loading history...</p>
          ) : sortedHistory.length ? (
            <div className="history-list">
              {sortedHistory.map((item, index) => (
                <div
                  key={`${item.timestamp}-${item.reading}-${index}`}
                  className="history-item"
                  style={{ animationDelay: `${index * 0.04}s` }}
                >
                  <span>
                    <span className="history-reading">{item.reading} m3</span>
                    <span className="history-date">
                      {formatTimestamp(item.timestamp)}
                    </span>
                  </span>
                  <span className="history-date">#{index + 1}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="reading-meta">No history saved yet.</p>
          )}
        </div>
      </div>

      <div className="footer">
        <span>API endpoints:</span>
        <a className="link-pill" href="/latest">/latest</a>
        <a className="link-pill" href="/history">/history</a>
      </div>
    </div>
  );
};

ReactDOM.createRoot(document.getElementById("app")).render(<App />);

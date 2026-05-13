function formatConfidence(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  const percent = Math.round(Number(value) * 100);
  return Math.max(0, Math.min(100, percent));
}

export default function ResultCard({
  action,
  reason,
  confidence,
  link,
  risk,
  news,
  destination,
}) {
  if (!action && !reason && confidence === undefined && !link) return null;

  const safeAction = action || "No action";
  const safeReason = reason || "No reason provided";
  const confidenceValue = formatConfidence(confidence);
  const confidenceLabel =
    confidenceValue === null ? "—" : `${confidenceValue}%`;

  const getActionColor = (actionType) => {
    if (!actionType) return "bg-slate-200 text-slate-500";
    const actionLower = actionType.toLowerCase();
    if (actionLower.includes("bus") && actionLower.includes("train")) {
      return "bg-amber-700 text-white hover:bg-amber-800";
    }
    if (actionLower.includes("flight")) {
      return "bg-purple-600 text-white hover:bg-purple-700";
    }
    if (actionLower.includes("train")) {
      return "bg-indigo-600 text-white hover:bg-indigo-700";
    }
    if (actionLower.includes("bus")) {
      return "bg-amber-600 text-white hover:bg-amber-700";
    }
    if (actionLower.includes("cab") || actionLower.includes("ride")) {
      return "bg-slate-900 text-white hover:bg-slate-800";
    }
    if (actionLower.includes("bike")) {
      return "bg-green-600 text-white hover:bg-green-700";
    }
    if (actionLower.includes("walk")) {
      return "bg-blue-600 text-white hover:bg-blue-700";
    }
    return "bg-slate-200 text-slate-500";
  };

  const getActionLink = (actionType, linkValue, destinationValue) => {
    if (!actionType) return "#";
    const actionLower = actionType.toLowerCase();
    if (actionLower.includes("bus") && actionLower.includes("train")) {
      return "https://www.google.com/travel/";
    }
    if (actionLower.includes("flight")) {
      return "https://www.google.com/flights";
    }
    if (actionLower.includes("train")) {
      return "https://www.irctc.co.in";
    }
    if (actionLower.includes("bus")) {
      return "https://www.redbus.in/";
    }
    if (actionLower.includes("cab") || actionLower.includes("ride")) {
      return linkValue || "#";
    }
    if (actionLower.includes("bike")) {
      return "https://www.google.com/maps/search/bike+sharing";
    }
    if (actionLower.includes("walk")) {
      return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(destinationValue || '')}`;
    }
    return "#";
  };

  const getActionLabel = (actionType) => {
    if (!actionType) return "No Action";
    const actionLower = actionType.toLowerCase();
    if (actionLower.includes("bus") && actionLower.includes("train")) {
      return "Plan Intercity Trip";
    }
    if (actionLower.includes("flight")) {
      return "Search Flights";
    }
    if (actionLower.includes("train")) {
      return "Book Train";
    }
    if (actionLower.includes("bus")) {
      return "Find Buses";
    }
    if (actionLower.includes("cab") || actionLower.includes("ride")) {
      return "Book Uber";
    }
    if (actionLower.includes("bike")) {
      return "Find Bike";
    }
    if (actionLower.includes("walk")) {
      return "Get Directions";
    }
    return "Take Action";
  };

  const buttonColor = getActionColor(safeAction);
  const actionLink = getActionLink(safeAction, link, destination);
  const actionLabel = getActionLabel(safeAction);
  const isDisabled = !link && !safeAction.toLowerCase().includes("walk") && !safeAction.toLowerCase().includes("bike") && !safeAction.toLowerCase().includes("flight") && !safeAction.toLowerCase().includes("train") && !safeAction.toLowerCase().includes("bus");

  const riskLevel = risk?.level ? risk.level.toUpperCase() : null;
  const showRisk = risk && (risk.relevant || risk?.level === "high" || risk?.level === "medium");
  const newsItems = news?.articles?.slice(0, 3) || [];

  return (
    <div className="mt-6 rounded-2xl border border-slate-200 bg-white/90 p-6 shadow-lg transition-all duration-300">
      <p className="text-sm font-semibold uppercase tracking-wide text-slate-500">
        Recommendation
      </p>
      <h2 className="mt-3 text-3xl font-semibold text-slate-900 sm:text-4xl">
        {safeAction}
      </h2>
      <div className="mt-4 text-slate-700">
        <p className="text-xs font-semibold uppercase text-slate-400">Reason</p>
        <p className="mt-1 text-base">{safeReason}</p>
      </div>
      <div className="mt-5">
        <div className="flex items-center justify-between text-xs font-semibold uppercase text-slate-400">
          <span>Confidence</span>
          <span className="text-slate-600">{confidenceLabel}</span>
        </div>
        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-slate-900 transition-all"
            style={{ width: `${confidenceValue ?? 0}%` }}
          />
        </div>
      </div>
      <div className="mt-6">
        {isDisabled ? (
          <span
            className="inline-flex cursor-not-allowed items-center justify-center rounded-xl bg-slate-200 px-5 py-3 text-sm font-semibold text-slate-500 shadow-sm"
            aria-disabled="true"
          >
            {actionLabel}
          </span>
        ) : (
          <a
            href={actionLink}
            target={actionLink !== "#" ? "_blank" : "_self"}
            rel={actionLink !== "#" ? "noreferrer" : undefined}
            className={`inline-flex items-center justify-center rounded-xl px-5 py-3 text-sm font-semibold shadow-sm transition ${
              buttonColor
            }`}
          >
            {actionLabel}
          </a>
        )}
      </div>

      {showRisk ? (
        <div className="mt-6 rounded-xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <p className="text-xs font-semibold uppercase text-amber-700">
            Risk Analysis
          </p>
          <p className="mt-1 font-semibold">Level: {riskLevel}</p>
          {risk?.factors?.length ? (
            <ul className="mt-2 list-disc pl-5 text-amber-800">
              {risk.factors.map((factor, idx) => (
                <li key={`risk-${idx}`}>{factor}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-2">No major risk factors detected.</p>
          )}
        </div>
      ) : null}

      {newsItems.length ? (
        <div className="mt-6 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
          <p className="text-xs font-semibold uppercase text-slate-500">
            Relevant News
          </p>
          <ul className="mt-2 list-disc pl-5">
            {newsItems.map((item, idx) => (
              <li key={`news-${idx}`}>
                {item.title || "News headline"}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

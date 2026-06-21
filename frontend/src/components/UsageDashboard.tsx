import { useEffect, useMemo, useState } from "react";
import { Activity, BarChart3, Clock, Loader2 } from "lucide-react";
import { t, type Language } from "../i18n";
import { useSettingsStore } from "../stores/settingsStore";

export function UsageDashboard() {
  const {
    usageSummary,
    usageByProvider,
    usageByFunction,
    recentUsage,
    loadingUsage,
    fetchUsage,
    language,
  } = useSettingsStore();
  const [days, setDays] = useState(7);

  useEffect(() => {
    fetchUsage(days);
  }, [days, fetchUsage]);

  const maxProviderCalls = useMemo(
    () => Math.max(1, ...usageByProvider.map((item) => item.calls)),
    [usageByProvider]
  );

  return (
    <section className="rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <BarChart3 size={17} className="text-cyan-500" />
          {t(language, "usageDashboard")}
        </div>
        <div className="flex items-center gap-2">
          {loadingUsage && <Loader2 size={14} className="animate-spin text-muted-foreground" />}
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs"
          >
            <option value={7}>{t(language, "last7Days")}</option>
            <option value={30}>{t(language, "last30Days")}</option>
            <option value={90}>{t(language, "last90Days")}</option>
          </select>
        </div>
      </div>

      <div className="grid gap-4 p-4">
        <div className="grid gap-3 md:grid-cols-4">
          <Metric label={t(language, "today")} value={formatNumber(usageSummary?.calls_today || 0, language)} hint={t(language, "calls")} />
          <Metric label={t(language, "thisWeek")} value={formatNumber(usageSummary?.calls_week || 0, language)} hint={t(language, "calls")} />
          <Metric label={t(language, "input")} value={formatNumber(usageSummary?.tokens_in_week || 0, language)} hint={t(language, "tokens")} />
          <Metric label={t(language, "output")} value={formatNumber(usageSummary?.tokens_out_week || 0, language)} hint={t(language, "tokens")} />
        </div>

        {usageSummary && typeof usageSummary.cache_hit_rate === "number" && (
          <div className="grid gap-3 md:grid-cols-3">
            <Metric
              label={t(language, "cacheHitRate")}
              value={`${usageSummary.cache_hit_rate}%`}
              hint={t(language, "cacheHitRateHint")}
            />
            <div className="rounded-lg border border-border bg-background/60 p-3">
              <div className="text-xs text-muted-foreground">{t(language, "cacheTokens")}</div>
              <div className="mt-1 text-xs text-emerald-500">
                {t(language, "cacheHit")}: {formatNumber(usageSummary.cache_hit_tokens, language)}
              </div>
              <div className="text-xs text-amber-500">
                {t(language, "cacheMiss")}: {formatNumber(usageSummary.cache_miss_tokens, language)}
              </div>
            </div>
            <div className="rounded-lg border border-border bg-background/60 p-3">
              <div className="text-xs text-muted-foreground">{t(language, "estimatedCost")}</div>
              <div className="mt-1 text-xl font-semibold">¥ {usageSummary.estimated_cost.toFixed(2)}</div>
              {Object.entries(usageSummary.cost_by_model || {}).map(([model, cost]) => (
                <div key={model} className="text-[11px] text-muted-foreground">
                  {model}: ¥ {cost.total.toFixed(4)}
                </div>
              ))}
              <div className="text-[11px] text-muted-foreground">{t(language, "estimatedCostHint")}</div>
            </div>
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-lg border border-border p-3">
            <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <Activity size={14} />
              {t(language, "byProvider")}
            </div>
            <div className="space-y-3">
              {usageByProvider.length === 0 && <EmptyLine text={t(language, "noProviderUsage")} />}
              {usageByProvider.map((item) => {
                const cacheTotal = item.cache_hit_tokens + item.cache_miss_tokens;
                const cacheRate = cacheTotal > 0
                  ? Math.round(item.cache_hit_tokens / cacheTotal * 100)
                  : null;
                return (
                  <BarRow
                    key={`${item.provider_name}:${item.model}`}
                    label={item.provider_name || t(language, "defaultProvider")}
                    sublabel={`${item.model}${cacheRate === null ? "" : ` · ${t(language, "cacheHitRate")} ${cacheRate}%`}`}
                    value={item.calls}
                    width={(item.calls / maxProviderCalls) * 100}
                    tone="cyan"
                  />
                );
              })}
            </div>
          </div>

          <div className="rounded-lg border border-border p-3">
            <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <Activity size={14} />
              {t(language, "byFunction")}
            </div>
            <div className="space-y-3">
              {usageByFunction.length === 0 && <EmptyLine text={t(language, "noFunctionUsage")} />}
              {usageByFunction.map((item) => (
                <BarRow
                  key={item.function_name}
                  label={item.function_name}
                  sublabel={`${formatNumber(item.tokens_total, language)} ${t(language, "tokens")}`}
                  value={`${item.percentage}%`}
                  width={item.percentage}
                  tone="violet"
                />
              ))}
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-border">
          <div className="flex items-center gap-2 border-b border-border px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            <Clock size={14} />
            {t(language, "recentCalls")}
          </div>
          <div className="max-h-72 overflow-auto">
            {recentUsage.length === 0 ? (
              <EmptyLine text={t(language, "noRecentCalls")} />
            ) : (
              recentUsage.map((record) => (
                <div key={record.id} className="grid min-w-[760px] grid-cols-[88px_1fr_90px_110px_170px] gap-3 border-b border-border px-3 py-2 text-xs last:border-b-0">
                  <span className="text-muted-foreground">{formatTime(record.timestamp, language)}</span>
                  <span className="min-w-0 truncate">
                    {record.provider_name || t(language, "defaultProvider")} / {record.model || t(language, "unknown")}
                  </span>
                  <span className="text-muted-foreground">{record.function_name}</span>
                  <span className="flex items-center justify-end gap-2 text-muted-foreground">
                    <span className={record.status === "success" ? "h-2 w-2 rounded-full bg-green-500" : "h-2 w-2 rounded-full bg-red-500"} />
                    {formatNumber(record.tokens_in, language)}/{formatNumber(record.tokens_out, language)}
                  </span>
                  {record.cache_hit_tokens != null || record.cache_miss_tokens != null ? (
                    <span className="text-right text-emerald-500">
                      {t(language, "cacheHit")} {formatNumber(record.cache_hit_tokens || 0, language)} / {t(language, "cacheMiss")} {formatNumber(record.cache_miss_tokens || 0, language)}
                    </span>
                  ) : (
                    <span className="text-right text-muted-foreground">{t(language, "noCacheData")}</span>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function Metric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-semibold">{value}</div>
      <div className="text-[11px] text-muted-foreground">{hint}</div>
    </div>
  );
}

function BarRow({
  label,
  sublabel,
  value,
  width,
  tone,
}: {
  label: string;
  sublabel: string;
  value: number | string;
  width: number;
  tone: "cyan" | "violet";
}) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-3 text-xs">
        <div className="min-w-0">
          <div className="truncate font-medium">{label}</div>
          <div className="truncate text-muted-foreground">{sublabel}</div>
        </div>
        <div className="text-muted-foreground">{value}</div>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div
          className={tone === "cyan" ? "h-full rounded-full bg-cyan-500" : "h-full rounded-full bg-violet-500"}
          style={{ width: `${Math.max(4, Math.min(100, width))}%` }}
        />
      </div>
    </div>
  );
}

function EmptyLine({ text }: { text: string }) {
  return <div className="px-3 py-6 text-center text-xs text-muted-foreground">{text}</div>;
}

function formatNumber(value: number, language: Language) {
  return new Intl.NumberFormat(language === "zh" ? "zh-CN" : "en", {
    notation: value >= 10000 ? "compact" : "standard",
  }).format(value);
}

function formatTime(timestamp: string, language: Language) {
  if (!timestamp) return "-";
  return new Date(timestamp).toLocaleTimeString(language === "zh" ? "zh-CN" : "en", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

import type { IndicatorParamSpec } from '@/services/api';

interface Props {
  parameters: IndicatorParamSpec[];
  values: Record<string, number | string>;
  onChange: (name: string, value: number | string) => void;
}

const inputCls =
  'min-h-[36px] w-full rounded border border-line bg-surface px-2.5 text-xs text-ink focus:border-cyan focus:outline-none';

export function DynamicParamFields({ parameters, values, onChange }: Props) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {parameters.map((p) => {
        const current = values[p.name] ?? p.default;
        return (
          <label key={p.name} className="space-y-1 text-xs">
            <span className="text-mute">{p.label}</span>
            {p.param_type === 'select' && p.options ? (
              <select
                value={String(current)}
                onChange={(e) => onChange(p.name, e.target.value)}
                className={inputCls}
              >
                {p.options.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="number"
                step={p.param_type === 'float' ? '0.1' : '1'}
                min={p.min_val ?? undefined}
                max={p.max_val ?? undefined}
                value={current}
                onChange={(e) => {
                  const num = p.param_type === 'float' ? parseFloat(e.target.value) : parseInt(e.target.value, 10);
                  onChange(p.name, Number.isFinite(num) ? num : p.default);
                }}
                className={`${inputCls} tabular-nums`}
              />
            )}
          </label>
        );
      })}
    </div>
  );
}

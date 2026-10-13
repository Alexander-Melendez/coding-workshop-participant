import PropTypes from 'prop-types';
import { clampPct, formatMoney } from '../lib/format.js';

/**
 * Spent vs forecast vs budget on one bar.
 * Solid = spent so far, hatched = forecast (spent + remaining assigned work),
 * vertical tick = budget. The bar turns red once spending passes the budget.
 */
export default function BudgetGauge({
  budget, spent, forecast, large,
}) {
  const scale = Math.max(budget, spent, forecast, 1);
  const over = spent > budget;
  const forecastOver = !over && forecast > budget;
  const label = `${formatMoney(spent)} spent of ${formatMoney(budget)} budget; forecast ${formatMoney(forecast)}`;

  return (
    <div className={`gauge ${over ? 'gauge--over' : ''} ${large ? 'gauge--large' : ''}`}>
      <div className="gauge-track" role="img" aria-label={label}>
        <span className="gauge-forecast" style={{ width: `${clampPct((forecast / scale) * 100)}%` }} />
        <span className="gauge-spent" style={{ width: `${clampPct((spent / scale) * 100)}%` }} />
        <span className="gauge-budget" style={{ left: `calc(${clampPct((budget / scale) * 100)}% - 1px)` }} />
      </div>
      <div className="gauge-legend">
        <span className={over ? 'over' : ''}>
          {formatMoney(spent)}
          {' '}
          spent of
          {' '}
          {formatMoney(budget)}
        </span>
        <span className={forecastOver || over ? 'over' : 'muted'}>
          Forecast
          {' '}
          {formatMoney(forecast)}
        </span>
      </div>
    </div>
  );
}

BudgetGauge.propTypes = {
  budget: PropTypes.number.isRequired,
  spent: PropTypes.number.isRequired,
  forecast: PropTypes.number.isRequired,
  large: PropTypes.bool,
};

/** Simple 0-100% bar. */
export function ProgressBar({ value, tone, label }) {
  return (
    <div
      className={`progress ${tone ? `progress--${tone}` : ''}`}
      role="progressbar"
      aria-valuenow={Math.round(value)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <span style={{ width: `${clampPct(value)}%` }} />
    </div>
  );
}

ProgressBar.propTypes = {
  value: PropTypes.number.isRequired,
  tone: PropTypes.oneOf(['ink', 'over']),
  label: PropTypes.string.isRequired,
};

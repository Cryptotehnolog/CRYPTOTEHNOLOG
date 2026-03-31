import { useMemo } from "react";

import {
  filterPositionHistoryRows,
  filterPositionHistoryRowsByExchange,
  mapPositionHistoryToTerminalRow,
  sortPositionHistoryRows,
} from "../lib/positionHistoryColumns";
import type { PositionHistoryResponse } from "../../../shared/types/dashboard";

type HistorySortMode = "recent" | "result-desc" | "result-asc";

type TerminalExchangeOption = {
  name: string;
};

type UsePositionHistoryViewModelOptions = {
  data: PositionHistoryResponse | undefined;
  pairQuery: string;
  exchangeFilter: string;
  strategyFilter: string;
  sortMode: HistorySortMode;
  terminalExchanges: TerminalExchangeOption[];
};

export function usePositionHistoryViewModel(
  options: UsePositionHistoryViewModelOptions,
) {
  const rows = useMemo(() => {
    const mapped = options.data?.positions.map(mapPositionHistoryToTerminalRow) ?? [];
    const filteredByPair = filterPositionHistoryRows(mapped, options.pairQuery);
    const filteredByExchange = filterPositionHistoryRowsByExchange(
      filteredByPair,
      options.exchangeFilter,
    );
    const filteredByStrategy =
      options.strategyFilter === "all"
        ? filteredByExchange
        : filteredByExchange.filter(
            (row) => row.strategy?.trim().toLowerCase() === options.strategyFilter,
          );
    return sortPositionHistoryRows(filteredByStrategy, options.sortMode);
  }, [
    options.data?.positions,
    options.exchangeFilter,
    options.pairQuery,
    options.sortMode,
    options.strategyFilter,
  ]);

  const exchangeOptions = useMemo(() => {
    return options.terminalExchanges
      .map((exchange) => exchange.name)
      .sort((left, right) => left.localeCompare(right));
  }, [options.terminalExchanges]);

  const strategyOptions = useMemo(() => {
    const strategies = new Set<string>();
    for (const position of options.data?.positions ?? []) {
      if (typeof position.strategy === "string" && position.strategy.trim()) {
        strategies.add(position.strategy.trim());
      }
    }
    return Array.from(strategies).sort((left, right) => left.localeCompare(right));
  }, [options.data?.positions]);

  return {
    rows,
    exchangeOptions,
    strategyOptions,
  };
}

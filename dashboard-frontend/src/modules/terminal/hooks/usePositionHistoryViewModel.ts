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
    return sortPositionHistoryRows(filteredByExchange, options.sortMode);
  }, [options.data?.positions, options.exchangeFilter, options.pairQuery, options.sortMode]);

  const exchangeOptions = useMemo(() => {
    return options.terminalExchanges
      .map((exchange) => exchange.name)
      .sort((left, right) => left.localeCompare(right));
  }, [options.terminalExchanges]);

  return {
    rows,
    exchangeOptions,
  };
}

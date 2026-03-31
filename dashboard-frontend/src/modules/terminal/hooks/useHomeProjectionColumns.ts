import { useEffect, useState } from "react";

type UseHomeProjectionColumnsOptions<TColumnKey extends string> = {
  loadPersisted: () => TColumnKey[];
  sanitize: (value: unknown) => TColumnKey[];
  storageKey: string;
  lockedKeys: ReadonlySet<TColumnKey>;
};

export function useHomeProjectionColumns<TColumnKey extends string>(
  options: UseHomeProjectionColumnsOptions<TColumnKey>,
) {
  const [columns, setColumns] = useState<TColumnKey[]>(() => options.loadPersisted());

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(options.storageKey, JSON.stringify(columns));
  }, [columns, options.storageKey]);

  const toggleColumn = (columnKey: TColumnKey) => {
    if (options.lockedKeys.has(columnKey)) {
      return;
    }

    setColumns((current) => {
      const isSelected = current.includes(columnKey);
      const next = isSelected
        ? current.filter((item) => item !== columnKey)
        : [...current, columnKey];

      return options.sanitize(next);
    });
  };

  const isSelected = (columnKey: TColumnKey) => columns.includes(columnKey);

  return {
    columns,
    setColumns,
    toggleColumn,
    isSelected,
  };
}

import {
  keyLabel,
  keyValue,
  keyValueItem,
  keyValueList,
} from "./KeyValueList.css";

type KeyValue = {
  label: string;
  value: string | number;
};

type KeyValueListProps = {
  items: KeyValue[];
};

export function KeyValueList({ items }: KeyValueListProps) {
  return (
    <div className={keyValueList}>
      {items.map((item) => (
        <div key={item.label} className={keyValueItem}>
          <span className={keyLabel}>{item.label}</span>
          <span className={keyValue}>{item.value}</span>
        </div>
      ))}
    </div>
  );
}

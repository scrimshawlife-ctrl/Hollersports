import type { ReactNode, KeyboardEvent } from "react";

export type Column<T> = {
  key: string;
  header: string;
  align?: "left" | "right";
  tabular?: boolean;
  render: (row: T, index: number) => ReactNode;
};

export type DataTableProps<T> = {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string;
  emptyMessage?: string;
  selectedKeys?: Set<string>;
  onToggleRow?: (key: string, row: T) => void;
  selectable?: boolean;
};

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  emptyMessage = "No rows",
  selectedKeys,
  onToggleRow,
  selectable = false,
}: DataTableProps<T>) {
  function onKeyDown(e: KeyboardEvent<HTMLTableRowElement>, key: string, row: T) {
    if (!selectable || !onToggleRow) return;
    if (e.key === " " || e.key === "Enter") {
      e.preventDefault();
      onToggleRow(key, row);
    }
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {selectable && <th scope="col" style={{ width: 36 }} aria-label="Select" />}
            {columns.map((col) => (
              <th
                key={col.key}
                scope="col"
                style={col.align === "right" ? { textAlign: "right" } : undefined}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td
                className="empty-cell"
                colSpan={columns.length + (selectable ? 1 : 0)}
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row, i) => {
              const key = rowKey(row, i);
              const selected = selectedKeys?.has(key) ?? false;
              return (
                <tr
                  key={key}
                  tabIndex={selectable ? 0 : undefined}
                  aria-selected={selectable ? selected : undefined}
                  onClick={
                    selectable && onToggleRow
                      ? () => onToggleRow(key, row)
                      : undefined
                  }
                  onKeyDown={
                    selectable
                      ? (e) => onKeyDown(e, key, row)
                      : undefined
                  }
                >
                  {selectable && (
                    <td>
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => onToggleRow?.(key, row)}
                        onClick={(e) => e.stopPropagation()}
                        aria-label={`Select ${key}`}
                      />
                    </td>
                  )}
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={col.tabular ? "tabular" : undefined}
                      style={
                        col.align === "right" ? { textAlign: "right" } : undefined
                      }
                    >
                      {col.render(row, i)}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

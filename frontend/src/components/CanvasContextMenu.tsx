import { CSSProperties } from 'react';

export interface ContextMenuItem {
  id: string;
  label: string;
  onSelect: () => void;
}

interface CanvasContextMenuProps {
  x: number;
  y: number;
  items: ContextMenuItem[];
  onClose: () => void;
}

const menuStyle: CSSProperties = {
  position: 'fixed',
  minWidth: 180,
  background: '#1f2937',
  border: '1px solid #374151',
  borderRadius: 8,
  boxShadow: '0 8px 20px rgba(0,0,0,0.35)',
  zIndex: 999
};

export function CanvasContextMenu({ x, y, items, onClose }: CanvasContextMenuProps) {
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 998 }} onClick={onClose} onContextMenu={onClose}>
      <div style={{ ...menuStyle, left: x, top: y }} role="menu" onClick={(event) => event.stopPropagation()}>
        {items.map((item) => (
          <button
            key={item.id}
            onClick={() => {
              item.onSelect();
              onClose();
            }}
            style={{
              width: '100%',
              background: 'transparent',
              border: 0,
              color: '#f9fafb',
              textAlign: 'left',
              padding: '10px 12px',
              cursor: 'pointer'
            }}
          >
            {item.label}
          </button>
        ))}
      </div>
    </div>
  );
}

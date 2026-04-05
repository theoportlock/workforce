import { useEffect, useRef, useState } from 'react';

export type MenuAction = () => void;

export interface MenuItem {
  label: string;
  action?: MenuAction;
  disabled?: boolean;
  divider?: boolean;
}

export interface Menu {
  label: string;
  items: MenuItem[];
}

interface MenuBarProps {
  menus: Menu[];
}

export function MenuBar({ menus }: MenuBarProps) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const menuBarRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuBarRef.current && !menuBarRef.current.contains(e.target as Node)) {
        setOpenIndex(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleItemClick = (item: MenuItem) => {
    if (item.disabled || item.divider) return;
    item.action?.();
    setOpenIndex(null);
  };

  return (
    <div ref={menuBarRef} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      {menus.map((menu, idx) => (
        <div key={menu.label} style={{ position: 'relative' }}>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setOpenIndex(openIndex === idx ? null : idx);
            }}
            style={{
              background: openIndex === idx ? '#334155' : 'transparent',
              border: 'none',
              color: '#e2e8f0',
              cursor: 'pointer',
              padding: '4px 10px',
              borderRadius: 4,
              fontSize: 13,
              fontFamily: 'inherit'
            }}
          >
            {menu.label}
          </button>
          {openIndex === idx && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                marginTop: 4,
                background: '#1e293b',
                border: '1px solid #334155',
                borderRadius: 6,
                minWidth: 160,
                padding: '4px 0',
                zIndex: 1000,
                boxShadow: '0 10px 40px rgba(0,0,0,0.5)'
              }}
            >
              {menu.items.map((item, i) =>
                item.divider ? (
                  <div
                    key={`div-${i}`}
                    style={{ height: 1, background: '#334155', margin: '4px 8px' }}
                  />
                ) : (
                  <button
                    key={item.label}
                    onClick={() => handleItemClick(item)}
                    disabled={item.disabled}
                    style={{
                      display: 'block',
                      width: '100%',
                      textAlign: 'left',
                      background: 'transparent',
                      border: 'none',
                      color: item.disabled ? '#64748b' : '#e2e8f0',
                      cursor: item.disabled ? 'default' : 'pointer',
                      padding: '5px 14px',
                      fontSize: 13,
                      fontFamily: 'inherit'
                    }}
                  >
                    {item.label}
                  </button>
                )
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
import { useState } from "react";

const navItems = [
  { id: "landing", label: "Home" },
  { id: "input", label: "Decode Salary" },
  { id: "compare", label: "Compare Offers" },
  { id: "spendable", label: "Spendable Money" },
  { id: "pf", label: "PF & Gratuity" },
];

interface NavProps {
  screen: string;
  onNav: (s: string) => void;
}

export default function Nav({ screen, onNav }: NavProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <nav className="sticky top-0 z-50 bg-white/90 backdrop-blur border-b border-[#E2E5F0]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 flex items-center justify-between h-14">
        <button
          onClick={() => onNav("landing")}
          className="flex items-center gap-2 font-bold text-[#3730A3] text-base"
          style={{ fontFamily: "Manrope, sans-serif" }}
        >
          <span className="w-7 h-7 rounded-lg bg-[#3730A3] flex items-center justify-center text-white text-xs font-bold">₹</span>
          <span>Salary Decode India</span>
        </button>

        {/* Desktop nav */}
        <div className="hidden md:flex items-center gap-1">
          {navItems.map(item => (
            <button
              key={item.id}
              onClick={() => onNav(item.id)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                screen === item.id
                  ? "bg-[#EEF2FF] text-[#3730A3]"
                  : "text-[#64748B] hover:text-[#3730A3] hover:bg-[#F5F6FA]"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {/* Mobile menu toggle */}
        <button
          className="md:hidden p-2 rounded-lg text-[#64748B] hover:bg-[#F5F6FA]"
          onClick={() => setMenuOpen(v => !v)}
          aria-label="Menu"
        >
          <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            {menuOpen
              ? <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              : <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />}
          </svg>
        </button>
      </div>

      {menuOpen && (
        <div className="md:hidden border-t border-[#E2E5F0] bg-white px-4 py-3 flex flex-col gap-1">
          {navItems.map(item => (
            <button
              key={item.id}
              onClick={() => { onNav(item.id); setMenuOpen(false); }}
              className={`px-3 py-2 rounded-lg text-sm font-medium text-left transition-colors ${
                screen === item.id
                  ? "bg-[#EEF2FF] text-[#3730A3]"
                  : "text-[#64748B] hover:text-[#3730A3]"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </nav>
  );
}

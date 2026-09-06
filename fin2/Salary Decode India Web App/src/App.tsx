import { useState, useEffect, useRef, useCallback } from "react";
import Nav from "./components/Nav";
import Landing from "./screens/Landing";
import InputScreen from "./screens/InputScreen";
import ParsedReview from "./screens/ParsedReview";
import SalaryBreakdown from "./screens/SalaryBreakdown";
import TaxScenarios from "./screens/TaxScenarios";
import SpendableMoney from "./screens/SpendableMoney";
import CompareOffers from "./screens/CompareOffers";
import PFGratuity from "./screens/PFGratuity";
import AskAIPanel from "./components/AskAIPanel";
import { defaultSalaryData } from "./data/sampleData";
import type { SalaryData } from "./data/sampleData";
import { fetchBreakdown, fetchSampleOffers } from "./lib/api";
import { salaryDataToCtcBreakup, sampleOfferToSalaryData } from "./lib/mapping";
import type { BreakdownResponse, ParsedOfferAI } from "./lib/types";

type Screen = "landing" | "input" | "review" | "breakdown" | "tax" | "spendable" | "compare" | "pf";
type InputTab = "upload" | "paste" | "manual";

export default function App() {
  const [screen, setScreen] = useState<Screen>("landing");
  const [salaryData, setSalaryData] = useState<SalaryData>(defaultSalaryData);
  const [parsedOffer, setParsedOffer] = useState<ParsedOfferAI | null>(null);
  const [breakdown, setBreakdown] = useState<BreakdownResponse | null>(null);
  const [breakdownLoading, setBreakdownLoading] = useState(false);
  const [breakdownError, setBreakdownError] = useState<string | null>(null);
  const [visible, setVisible] = useState(true);
  const [inputInitialTab, setInputInitialTab] = useState<InputTab>("manual");
  const [sampleLoading, setSampleLoading] = useState(false);
  const pendingScreen = useRef<Screen | null>(null);

  const runBreakdown = useCallback(async (data: SalaryData) => {
    setBreakdownLoading(true);
    setBreakdownError(null);
    try {
      const result = await fetchBreakdown(salaryDataToCtcBreakup(data), data.regime);
      setBreakdown(result);
    } catch {
      setBreakdownError("Couldn't reach the calculation engine. Is the backend running?");
    } finally {
      setBreakdownLoading(false);
    }
  }, []);

  const navigate = (s: string) => {
    const next = s as Screen;
    if (next === screen) return;
    setVisible(false);
    pendingScreen.current = next;
  };

  useEffect(() => {
    if (!visible && pendingScreen.current) {
      const t = setTimeout(() => {
        setScreen(pendingScreen.current!);
        pendingScreen.current = null;
        setVisible(true);
        window.scrollTo({ top: 0, behavior: "smooth" });
      }, 200);
      return () => clearTimeout(t);
    }
  }, [visible]);

  const handleInputContinue = (data: SalaryData, parsed?: ParsedOfferAI) => {
    setSalaryData(data);
    setParsedOffer(parsed ?? null);
    navigate("review");
    runBreakdown(data);
  };

  // User corrects an AI-extracted (or manually entered) field on the review
  // screen — re-run the deterministic engine against the corrected value.
  const handleCorrectField = (key: keyof SalaryData, value: number) => {
    setSalaryData(prev => {
      const next = { ...prev, [key]: value };
      runBreakdown(next);
      return next;
    });
  };

  const handleNavToInput = (tab: InputTab) => {
    setInputInitialTab(tab);
    navigate("input");
  };

  // "Try with a sample offer" / feature-card shortcuts — load a real sample
  // from the backend and run the real engine, rather than jumping to a
  // results screen with no data (which would just spin forever).
  const handleTrySample = async (targetScreen: string) => {
    setSampleLoading(true);
    try {
      const samples = await fetchSampleOffers();
      const sample = samples.find(s => s.id === "fresher_nonmetro_clean") ?? samples[0];
      const data = sampleOfferToSalaryData(sample);
      setSalaryData(data);
      setParsedOffer(null);
      navigate(targetScreen);
      runBreakdown(data);
    } catch {
      setBreakdownError("Couldn't load a sample offer. Is the backend running?");
      navigate("input");
    } finally {
      setSampleLoading(false);
    }
  };

  const navItems: Screen[] = ["landing", "input", "compare", "spendable", "pf"];
  const showNav = screen !== "landing" || true;

  const renderScreen = () => {
    switch (screen) {
      case "landing":
        return <Landing onNavToInput={handleNavToInput} onTrySample={handleTrySample} loadingSample={sampleLoading} />;
      case "input":
        return (
          <InputScreen
            initialTab={inputInitialTab}
            initialData={salaryData}
            onContinue={handleInputContinue}
          />
        );
      case "review":
        return (
          <ParsedReview
            data={salaryData}
            parsed={parsedOffer}
            breakdown={breakdown}
            loading={breakdownLoading}
            error={breakdownError}
            onCorrectField={handleCorrectField}
            onContinue={() => navigate("breakdown")}
            onBack={() => navigate("input")}
          />
        );
      case "breakdown":
        return (
          <SalaryBreakdown
            data={salaryData}
            breakdown={breakdown}
            loading={breakdownLoading}
            error={breakdownError}
            onNav={navigate}
          />
        );
      case "tax":
        return <TaxScenarios data={salaryData} onNav={navigate} />;
      case "spendable":
        return <SpendableMoney inHandMonthly={breakdown?.breakdown.in_hand_monthly ?? 0} onNav={navigate} />;
      case "compare":
        return <CompareOffers primaryData={salaryData} onNav={navigate} />;
      case "pf":
        return <PFGratuity data={salaryData} onNav={navigate} />;
      default:
        return null;
    }
  };

  return (
    <div className="min-h-full bg-[#F5F6FA]">
      <Nav screen={screen} onNav={navigate} />
      <main
        style={{
          opacity: visible ? 1 : 0,
          transform: visible ? "translateY(0)" : "translateY(8px)",
          transition: "opacity 250ms ease, transform 250ms ease",
        }}
      >
        {renderScreen()}
      </main>

      {/* Footer */}
      <footer className="border-t border-[#E2E5F0] bg-white mt-16 py-8 px-4 text-center">
        <div className="flex items-center justify-center gap-2 mb-3">
          <span className="w-6 h-6 rounded-lg bg-[#3730A3] flex items-center justify-center text-white text-xs font-bold">₹</span>
          <span className="font-bold text-[#3730A3] text-sm" style={{ fontFamily: "Manrope, sans-serif" }}>Salary Decode India</span>
        </div>
        <p className="text-xs text-[#94A3B8] max-w-md mx-auto leading-relaxed">
          All calculations are estimates for informational purposes only. Tax, PF, and gratuity figures depend on your specific situation. This is not financial or legal advice.
          Your figures are sent to our calculation engine only to compute this estimate — they are not stored.
        </p>
        <div className="flex items-center justify-center gap-4 mt-4 text-xs text-[#94A3B8]">
          {[
            { label: "Decode Salary", screen: "input" },
            { label: "Compare Offers", screen: "compare" },
            { label: "Spendable Money", screen: "spendable" },
            { label: "PF & Gratuity", screen: "pf" },
          ].map(link => (
            <button
              key={link.screen}
              onClick={() => navigate(link.screen)}
              className="hover:text-[#3730A3] transition-colors"
            >
              {link.label}
            </button>
          ))}
        </div>
      </footer>

      {screen !== "landing" && screen !== "input" && (
        <AskAIPanel ctcBreakup={salaryDataToCtcBreakup(salaryData)} />
      )}
    </div>
  );
}

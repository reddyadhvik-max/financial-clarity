export const fmt = (n: number) =>
  "₹" + n.toLocaleString("en-IN");

export const fmtK = (n: number) => {
  if (n >= 100000) return "₹" + (n / 100000).toFixed(n % 100000 === 0 ? 0 : 1) + "L";
  if (n >= 1000) return "₹" + (n / 1000).toFixed(0) + "K";
  return "₹" + n;
};

export interface SalaryData {
  company: string;
  jobTitle: string;
  city: string;
  ctc: number;
  basic: number;
  hra: number;
  specialAllowance: number;
  employerPF: number;
  employeePF: number;
  gratuity: number;
  variablePay: number;
  joiningBonus: number;
  professionalTax: number;
  healthInsurance: number;
  regime: "old" | "new";
  section80C: number;
  section80D: number;
  monthlyRent: number;
}

export const defaultSalaryData: SalaryData = {
  company: "Infosys Limited",
  jobTitle: "Senior Software Engineer",
  city: "Bengaluru",
  ctc: 1200000,
  basic: 480000,
  hra: 192000,
  specialAllowance: 288000,
  employerPF: 57600,
  employeePF: 57600,
  gratuity: 23077,
  variablePay: 120000,
  joiningBonus: 0,
  professionalTax: 2400,
  healthInsurance: 6000,
  regime: "new",
  section80C: 150000,
  section80D: 25000,
  monthlyRent: 22000,
};


export default function InputBox({ label, placeholder, value, onChange }) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-slate-700">{label}</span>
      <input
        type="text"
        className="mt-2 w-full rounded-xl border border-slate-200 bg-white/70 px-4 py-3 text-slate-900 shadow-sm outline-none ring-0 transition focus:border-slate-300 focus:bg-white focus:shadow"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

export default function KromaLogo() {
  return (
    <a href="/" className="logo" style={{ textDecoration: 'none', padding: '0.25rem 0' }}>
      <svg width="100%" height="80" viewBox="140 55 400 120" role="img">
        <rect x="155" y="60" width="90" height="90" rx="20" fill="#1c1917" stroke="#eab308" strokeWidth="2"/>
        <path d="M175 78 L223 78 L237 92 L237 138 L175 138 Z" fill="#292524" stroke="#3c3330" strokeWidth="1"/>
        <path d="M223 78 L223 92 L237 92 Z" fill="#1c1917" stroke="#3c3330" strokeWidth="1"/>
        <rect x="188" y="92" width="7" height="34" rx="2" fill="#eab308"/>
        <path d="M195 109 L209 94" stroke="#eab308" strokeWidth="7" strokeLinecap="round" fill="none"/>
        <path d="M195 109 L211 126" stroke="#eab308" strokeWidth="7" strokeLinecap="round" fill="none"/>
        <line x1="188" y1="132" x2="205" y2="132" stroke="#eab308" strokeWidth="2" strokeLinecap="round" opacity="0.8"/>
        <line x1="188" y1="137" x2="217" y2="137" stroke="#eab308" strokeWidth="2" strokeLinecap="round" opacity="0.5"/>
        <line x1="188" y1="142" x2="211" y2="142" stroke="#eab308" strokeWidth="2" strokeLinecap="round" opacity="0.3"/>
        <text x="262" y="122" fontFamily="'Outfit', sans-serif" fontSize="58" fontWeight="800" fill="#fafaf9" letterSpacing="-2">Kroma</text>
        <circle cx="270" cy="72" r="5" fill="#eab308"/>
        <text x="265" y="152" fontFamily="'DM Mono', monospace" fontSize="13" fontWeight="500" fill="#eab308" letterSpacing="4">ASK. LEARN. KNOW.</text>
      </svg>
    </a>
  )
}

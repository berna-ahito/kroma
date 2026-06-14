export default function KromaLogo() {
  return (
    <a href="/" className="logo" style={{ textDecoration: 'none', padding: '0.25rem 0' }}>
      <svg width="100%" height="80" viewBox="0 0 420 120" role="img" aria-labelledby="kroma-logo-title kroma-logo-desc">
        <title id="kroma-logo-title">Kroma</title>
        <desc id="kroma-logo-desc">Kroma logo with a rounded-square geometric K mark and the ASK. LEARN. KNOW. tagline.</desc>
        <defs>
          <linearGradient id="kroma-react-mark-stroke" x1="8" y1="16" x2="92" y2="96" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#2DD4BF" />
            <stop offset="0.58" stopColor="#6B9EFF" />
            <stop offset="1" stopColor="#C8A24A" />
          </linearGradient>
          <linearGradient id="kroma-react-stem" x1="32" y1="26" x2="32" y2="78" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#2DD4BF" />
            <stop offset="1" stopColor="#0F766E" />
          </linearGradient>
          <linearGradient id="kroma-react-arm-top" x1="44" y1="28" x2="80" y2="52" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#2DD4BF" />
            <stop offset="1" stopColor="#6B9EFF" />
          </linearGradient>
          <linearGradient id="kroma-react-arm-bottom" x1="44" y1="50" x2="80" y2="78" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#0F766E" />
            <stop offset="1" stopColor="#6B9EFF" />
          </linearGradient>
          <linearGradient id="kroma-react-brass" x1="44" y1="49" x2="64" y2="64" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#D6B45F" />
            <stop offset="1" stopColor="#C8A24A" />
          </linearGradient>
          <filter id="kroma-react-soft-shadow" x="-20%" y="-20%" width="140%" height="150%">
            <feDropShadow dx="0" dy="8" stdDeviation="8" floodColor="#01060A" floodOpacity="0.32" />
          </filter>
        </defs>

        <g filter="url(#kroma-react-soft-shadow)">
          <rect x="8" y="14" width="92" height="92" rx="24" fill="#11171B" stroke="url(#kroma-react-mark-stroke)" strokeWidth="3.5" />
          <rect x="15" y="21" width="78" height="78" rx="19" fill="none" stroke="#34434B" strokeWidth="1" opacity="0.55" />
          <rect x="30" y="30" width="14" height="56" rx="2.5" fill="url(#kroma-react-stem)" />
          <path d="M44 58L72 30H88L55 64L44 58Z" fill="url(#kroma-react-arm-top)" />
          <path d="M44 62L56 50L88 86H71L44 62Z" fill="url(#kroma-react-arm-bottom)" />
          <path d="M50 58L63 70L52 73L42 62L50 58Z" fill="url(#kroma-react-brass)" />
        </g>

        <text x="124" y="60" fontFamily="Outfit, Inter, Arial, sans-serif" fontSize="50" fontWeight="800" fill="#F7F3EA" letterSpacing="-1.4">Kroma</text>
        <text x="126" y="88" fontFamily="'DM Mono', Consolas, monospace" fontSize="13" fontWeight="500" fill="#B8C2C8" letterSpacing="4">ASK. LEARN. KNOW.</text>
        <circle cx="397" cy="45" r="3.5" fill="#C8A24A" />
      </svg>
    </a>
  )
}

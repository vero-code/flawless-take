export function BrandLogo({ className = '' }: { className?: string }) {
  return (
    <div className={`brand-logo-container ${className}`}>
      <div className="brand-logo-flawless">
        F L <span className="brand-logo-caret">Ʌ</span> W L E S S
      </div>
      <div className="brand-logo-take">
        TAKE
      </div>
      <div className="brand-logo-line"></div>
    </div>
  )
}

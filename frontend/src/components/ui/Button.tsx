import { motion } from 'framer-motion';
import clsx from 'clsx';
import type { ReactNode } from 'react';

interface ButtonProps {
  children?: ReactNode;
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  icon?: ReactNode;
  iconPosition?: 'left' | 'right';
  className?: string;
  disabled?: boolean;
  onClick?: () => void;
  type?: 'button' | 'submit' | 'reset';
}

export const Button = ({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  iconPosition = 'left',
  className,
  disabled,
  onClick,
  type = 'button',
}: ButtonProps) => {
  const baseClasses =
    'inline-flex items-center justify-center gap-2 font-semibold rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-white';

  const variantClasses = {
    primary:
      'text-white relative overflow-hidden',
    secondary:
      'backdrop-blur-[var(--liquid-blur)] text-[var(--text-primary)] hover:text-[var(--accent-primary)] border',
    danger:
      'bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-700 hover:to-rose-700 text-white',
    ghost:
      'bg-transparent hover:backdrop-blur-sm text-[var(--text-secondary)] hover:text-[var(--accent-primary)]',
  };

  const sizeClasses = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-5 py-2.5 text-base',
    lg: 'px-7 py-3.5 text-lg',
  };

  const isDisabled = disabled || loading;

  return (
    <motion.button
      type={type}
      className={clsx(
        baseClasses,
        variantClasses[variant],
        sizeClasses[size],
        isDisabled && 'opacity-50 cursor-not-allowed',
        className
      )}
      style={variant === 'primary' ? {
        background: 'var(--gradient-primary)',
        boxShadow: '0 4px 20px rgba(99, 102, 241, 0.3)',
        borderRadius: 'var(--radius-full)'
      } : variant === 'secondary' ? {
        background: 'var(--liquid-bg)',
        borderColor: 'var(--border-color)',
        borderRadius: 'var(--radius-full)',
        boxShadow: 'var(--shadow-sm)'
      } : variant === 'danger' ? {
        boxShadow: '0 4px 20px rgba(239, 68, 68, 0.3)',
        borderRadius: 'var(--radius-full)'
      } : {
        borderRadius: 'var(--radius-full)'
      }}
      disabled={isDisabled}
      onClick={onClick}
      whileHover={!isDisabled ? { 
        scale: 1.03, 
        y: -3,
        boxShadow: variant === 'primary' ? '0 12px 40px rgba(99, 102, 241, 0.45)' : undefined
      } : undefined}
      whileTap={!isDisabled ? { scale: 0.98 } : undefined}
      transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
    >
      {variant === 'primary' && (
        <span className="absolute inset-0 rounded-[var(--radius-full)] bg-gradient-to-r from-white/25 to-transparent opacity-0 hover:opacity-100 transition-opacity duration-300" />
      )}
      {loading ? (
        <motion.span
          className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full"
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
        />
      ) : (
        <>
          {icon && iconPosition === 'left' && icon}
          {children}
          {icon && iconPosition === 'right' && icon}
        </>
      )}
    </motion.button>
  );
};

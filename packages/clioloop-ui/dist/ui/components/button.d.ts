import { type VariantProps } from 'class-variance-authority';
declare const buttonVariants: (props?: {
    destructive?: boolean;
    ghost?: boolean;
    invert?: boolean;
    outlined?: boolean;
    size?: "default" | "icon" | "sm" | "xs";
} & import("class-variance-authority/types").ClassProp) => string;
export declare const Button: ({ children, className, destructive, ghost, invert, outlined, prefix, size, suffix, ...props }: ButtonProps) => import("react").JSX.Element;
interface ButtonProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'prefix' | 'suffix'>, VariantProps<typeof buttonVariants> {
    prefix?: React.ReactNode;
    suffix?: React.ReactNode;
}
export {};

import { type VariantProps } from 'class-variance-authority';
import { type PolyProps } from '../../../utils';
declare const typographyVariants: (props?: {
    compressed?: boolean;
    courier?: boolean;
    expanded?: boolean;
    mondwest?: boolean;
    mono?: boolean;
    sans?: boolean;
    variant?: "lg" | "md" | "sm" | "xl";
} & import("class-variance-authority/types").ClassProp) => string;
export declare const Typography: import("../../..").PolyComponent<"span", OwnProps>;
type OwnProps = VariantProps<typeof typographyVariants>;
export type TypographyProps<T extends React.ElementType = 'span'> = PolyProps<T, OwnProps>;
export {};

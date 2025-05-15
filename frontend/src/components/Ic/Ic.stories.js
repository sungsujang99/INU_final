import { Ic } from ".";

export default {
  title: "Components/Ic",
  component: Ic,

  argTypes: {
    property1: {
      options: ["variant-5", "variant-2", "variant-3", "variant-4", "areai"],
      control: { type: "select" },
    },
  },
};

export const Default = {
  args: {
    property1: "variant-5",
  },
};

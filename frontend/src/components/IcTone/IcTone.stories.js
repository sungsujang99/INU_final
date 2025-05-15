import { IcTone } from ".";

export default {
  title: "Components/IcTone",
  component: IcTone,

  argTypes: {
    property1: {
      options: ["area", "password", "id"],
      control: { type: "select" },
    },
  },
};

export const Default = {
  args: {
    property1: "area",
    propertyAreaClassName: {},
  },
};

import { Btn } from ".";

export default {
  title: "Components/Btn",
  component: Btn,

  argTypes: {
    property1: {
      options: ["deactive", "active"],
      control: { type: "select" },
    },
  },
};

export const Default = {
  args: {
    property1: "deactive",
    className: {},
    divClassName: {},
    text: "Next",
  },
};

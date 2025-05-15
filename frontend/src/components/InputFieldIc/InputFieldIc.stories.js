import { InputFieldIc } from ".";

export default {
  title: "Components/InputFieldIc",
  component: InputFieldIc,

  argTypes: {
    property1: {
      options: ["disalbe", "active", "default", "focus", "error"],
      control: { type: "select" },
    },
  },
};

export const Default = {
  args: {
    property1: "disalbe",
    className: {},
    frameClassName: {},
    text: "login id",
    hasDiv: true,
  },
};

import { Menu } from ".";

export default {
  title: "Components/Menu",
  component: Menu,

  argTypes: {
    menu: {
      options: ["selected", "default"],
      control: { type: "select" },
    },
  },
};

export const Default = {
  args: {
    menu: "selected",
    className: {},
    text: "menu 1",
    text1: "menu 2",
  },
};

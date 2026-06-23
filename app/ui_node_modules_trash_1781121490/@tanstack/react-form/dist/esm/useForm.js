import { jsx } from "react/jsx-runtime";
import { FormApi, functionalUpdate } from "@tanstack/form-core";
import { useStore } from "@tanstack/react-store";
import { useState } from "react";
import { Field } from "./useField.js";
import { useIsomorphicLayoutEffect } from "./useIsomorphicLayoutEffect.js";
function LocalSubscribe({
  form,
  selector,
  children
}) {
  const data = useStore(form.store, selector);
  return functionalUpdate(children, data);
}
function useForm(opts) {
  const [formApi] = useState(() => {
    const api = new FormApi(opts);
    const extendedApi = api;
    extendedApi.Field = function APIField(props) {
      return /* @__PURE__ */ jsx(Field, { ...props, form: api });
    };
    extendedApi.Subscribe = (props) => {
      return /* @__PURE__ */ jsx(
        LocalSubscribe,
        {
          form: api,
          selector: props.selector,
          children: props.children
        }
      );
    };
    return extendedApi;
  });
  useIsomorphicLayoutEffect(formApi.mount, []);
  useStore(formApi.store, (state) => state.isSubmitting);
  useIsomorphicLayoutEffect(() => {
    formApi.update(opts);
  });
  return formApi;
}
export {
  useForm
};
//# sourceMappingURL=useForm.js.map

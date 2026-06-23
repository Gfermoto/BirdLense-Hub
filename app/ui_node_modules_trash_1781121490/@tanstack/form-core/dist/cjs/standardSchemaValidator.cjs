"use strict";
Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
function prefixSchemaToErrors(issues, transformErrors) {
  const schema = /* @__PURE__ */ new Map();
  for (const issue of issues) {
    const path = [...issue.path ?? []].map((segment) => {
      const normalizedSegment = typeof segment === "object" ? segment.key : segment;
      return typeof normalizedSegment === "number" ? `[${normalizedSegment}]` : normalizedSegment;
    }).join(".").replace(/\.\[/g, "[");
    schema.set(path, (schema.get(path) ?? []).concat(issue));
  }
  const transformedSchema = {};
  schema.forEach((value, key) => {
    transformedSchema[key] = transformErrors(value);
  });
  return transformedSchema;
}
function defaultFormTransformer(transformErrors) {
  return (issues) => ({
    form: transformErrors(issues),
    fields: prefixSchemaToErrors(issues, transformErrors)
  });
}
const standardSchemaValidator = (params = {}) => () => {
  const transformFieldErrors = params.transformErrors ?? ((issues) => issues.map((issue) => issue.message).join(", "));
  const getTransformStrategy = (validationSource) => validationSource === "form" ? defaultFormTransformer(transformFieldErrors) : transformFieldErrors;
  return {
    validate({ value, validationSource }, fn) {
      const result = fn["~standard"].validate(value);
      if (result instanceof Promise) {
        throw new Error("async function passed to sync validator");
      }
      if (!result.issues) return;
      const transformer = getTransformStrategy(validationSource);
      return transformer(result.issues);
    },
    async validateAsync({ value, validationSource }, fn) {
      const result = await fn["~standard"].validate(value);
      if (!result.issues) return;
      const transformer = getTransformStrategy(validationSource);
      return transformer(result.issues);
    }
  };
};
const isStandardSchemaValidator = (validator) => !!validator && "~standard" in validator;
exports.isStandardSchemaValidator = isStandardSchemaValidator;
exports.standardSchemaValidator = standardSchemaValidator;
//# sourceMappingURL=standardSchemaValidator.cjs.map

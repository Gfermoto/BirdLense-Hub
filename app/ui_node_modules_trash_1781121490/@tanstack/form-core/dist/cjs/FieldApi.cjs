"use strict";
Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
const store = require("@tanstack/store");
const standardSchemaValidator = require("./standardSchemaValidator.cjs");
const utils = require("./utils.cjs");
class FieldApi {
  /**
   * Initializes a new `FieldApi` instance.
   */
  constructor(opts) {
    this.options = {};
    this.mount = () => {
      var _a, _b;
      const cleanup = this.store.mount();
      const info = this.getInfo();
      info.instance = this;
      this.update(this.options);
      const { onMount } = this.options.validators || {};
      if (onMount) {
        const error = this.runValidator({
          validate: onMount,
          value: {
            value: this.state.value,
            fieldApi: this,
            validationSource: "field"
          },
          type: "validate"
        });
        if (error) {
          this.setMeta((prev) => ({
            ...prev,
            // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
            errorMap: { ...prev == null ? void 0 : prev.errorMap, onMount: error }
          }));
        }
      }
      (_b = (_a = this.options.listeners) == null ? void 0 : _a.onMount) == null ? void 0 : _b.call(_a, {
        value: this.state.value,
        fieldApi: this
      });
      return cleanup;
    };
    this.update = (opts2) => {
      if (this.state.value === void 0) {
        const formDefault = utils.getBy(opts2.form.options.defaultValues, opts2.name);
        if (opts2.defaultValue !== void 0) {
          this.setValue(opts2.defaultValue, {
            dontUpdateMeta: true
          });
        } else if (formDefault !== void 0) {
          this.setValue(formDefault, {
            dontUpdateMeta: true
          });
        }
      }
      if (this.form.getFieldMeta(this.name) === void 0) {
        this.setMeta(this.state.meta);
      }
      this.options = opts2;
      this.name = opts2.name;
    };
    this.getValue = () => {
      return this.form.getFieldValue(this.name);
    };
    this.setValue = (updater, options) => {
      var _a, _b;
      this.form.setFieldValue(this.name, updater, options);
      (_b = (_a = this.options.listeners) == null ? void 0 : _a.onChange) == null ? void 0 : _b.call(_a, {
        value: this.state.value,
        fieldApi: this
      });
      this.validate("change");
    };
    this.getMeta = () => this.store.state.meta;
    this.setMeta = (updater) => this.form.setFieldMeta(this.name, updater);
    this.getInfo = () => this.form.getFieldInfo(this.name);
    this.pushValue = (value, opts2) => this.form.pushFieldValue(this.name, value, opts2);
    this.insertValue = (index, value, opts2) => this.form.insertFieldValue(this.name, index, value, opts2);
    this.replaceValue = (index, value, opts2) => this.form.replaceFieldValue(this.name, index, value, opts2);
    this.removeValue = (index, opts2) => this.form.removeFieldValue(this.name, index, opts2);
    this.swapValues = (aIndex, bIndex, opts2) => this.form.swapFieldValues(this.name, aIndex, bIndex, opts2);
    this.moveValue = (aIndex, bIndex, opts2) => this.form.moveFieldValues(this.name, aIndex, bIndex, opts2);
    this.getLinkedFields = (cause) => {
      const fields = Object.values(this.form.fieldInfo);
      const linkedFields = [];
      for (const field of fields) {
        if (!field.instance) continue;
        const { onChangeListenTo, onBlurListenTo } = field.instance.options.validators || {};
        if (cause === "change" && (onChangeListenTo == null ? void 0 : onChangeListenTo.includes(this.name))) {
          linkedFields.push(field.instance);
        }
        if (cause === "blur" && (onBlurListenTo == null ? void 0 : onBlurListenTo.includes(this.name))) {
          linkedFields.push(field.instance);
        }
      }
      return linkedFields;
    };
    this.validateSync = (cause, errorFromForm) => {
      const validates = utils.getSyncValidatorArray(cause, this.options);
      const linkedFields = this.getLinkedFields(cause);
      const linkedFieldValidates = linkedFields.reduce(
        (acc, field) => {
          const fieldValidates = utils.getSyncValidatorArray(cause, field.options);
          fieldValidates.forEach((validate) => {
            validate.field = field;
          });
          return acc.concat(fieldValidates);
        },
        []
      );
      let hasErrored = false;
      store.batch(() => {
        const validateFieldFn = (field, validateObj) => {
          const errorMapKey = getErrorMapKey(validateObj.cause);
          const error = (
            /*
              If `validateObj.validate` is `undefined`, then the field doesn't have
              a validator for this event, but there still could be an error that
              needs to be cleaned up related to the current event left by the
              form's validator.
            */
            validateObj.validate ? normalizeError(
              field.runValidator({
                validate: validateObj.validate,
                value: {
                  value: field.store.state.value,
                  validationSource: "field",
                  fieldApi: field
                },
                type: "validate"
              })
            ) : errorFromForm[errorMapKey]
          );
          if (field.state.meta.errorMap[errorMapKey] !== error) {
            field.setMeta((prev) => ({
              ...prev,
              errorMap: {
                ...prev.errorMap,
                [getErrorMapKey(validateObj.cause)]: (
                  // Prefer the error message from the field validators if they exist
                  error ? error : errorFromForm[errorMapKey]
                )
              }
            }));
          }
          if (error || errorFromForm[errorMapKey]) {
            hasErrored = true;
          }
        };
        for (const validateObj of validates) {
          validateFieldFn(this, validateObj);
        }
        for (const fieldValitateObj of linkedFieldValidates) {
          if (!fieldValitateObj.validate) continue;
          validateFieldFn(fieldValitateObj.field, fieldValitateObj);
        }
      });
      const submitErrKey = getErrorMapKey("submit");
      if (this.state.meta.errorMap[submitErrKey] && cause !== "submit" && !hasErrored) {
        this.setMeta((prev) => ({
          ...prev,
          errorMap: {
            ...prev.errorMap,
            [submitErrKey]: void 0
          }
        }));
      }
      return { hasErrored };
    };
    this.validateAsync = async (cause, formValidationResultPromise) => {
      const validates = utils.getAsyncValidatorArray(cause, this.options);
      const asyncFormValidationResults = await formValidationResultPromise;
      const linkedFields = this.getLinkedFields(cause);
      const linkedFieldValidates = linkedFields.reduce(
        (acc, field) => {
          const fieldValidates = utils.getAsyncValidatorArray(cause, field.options);
          fieldValidates.forEach((validate) => {
            validate.field = field;
          });
          return acc.concat(fieldValidates);
        },
        []
      );
      if (!this.state.meta.isValidating) {
        this.setMeta((prev) => ({ ...prev, isValidating: true }));
      }
      for (const linkedField of linkedFields) {
        linkedField.setMeta((prev) => ({ ...prev, isValidating: true }));
      }
      const validatesPromises = [];
      const linkedPromises = [];
      const validateFieldAsyncFn = (field, validateObj, promises) => {
        const errorMapKey = getErrorMapKey(validateObj.cause);
        const fieldValidatorMeta = field.getInfo().validationMetaMap[errorMapKey];
        fieldValidatorMeta == null ? void 0 : fieldValidatorMeta.lastAbortController.abort();
        const controller = new AbortController();
        this.getInfo().validationMetaMap[errorMapKey] = {
          lastAbortController: controller
        };
        promises.push(
          new Promise(async (resolve) => {
            var _a;
            let rawError;
            try {
              rawError = await new Promise((rawResolve, rawReject) => {
                if (this.timeoutIds[validateObj.cause]) {
                  clearTimeout(this.timeoutIds[validateObj.cause]);
                }
                this.timeoutIds[validateObj.cause] = setTimeout(async () => {
                  if (controller.signal.aborted) return rawResolve(void 0);
                  try {
                    rawResolve(
                      await this.runValidator({
                        validate: validateObj.validate,
                        value: {
                          value: field.store.state.value,
                          fieldApi: field,
                          signal: controller.signal,
                          validationSource: "field"
                        },
                        type: "validateAsync"
                      })
                    );
                  } catch (e) {
                    rawReject(e);
                  }
                }, validateObj.debounceMs);
              });
            } catch (e) {
              rawError = e;
            }
            if (controller.signal.aborted) return resolve(void 0);
            const error = normalizeError(rawError);
            const fieldErrorFromForm = (_a = asyncFormValidationResults[this.name]) == null ? void 0 : _a[errorMapKey];
            const fieldError = error || fieldErrorFromForm;
            field.setMeta((prev) => {
              return {
                ...prev,
                errorMap: {
                  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
                  ...prev == null ? void 0 : prev.errorMap,
                  [errorMapKey]: fieldError
                }
              };
            });
            resolve(fieldError);
          })
        );
      };
      for (const validateObj of validates) {
        if (!validateObj.validate) continue;
        validateFieldAsyncFn(this, validateObj, validatesPromises);
      }
      for (const fieldValitateObj of linkedFieldValidates) {
        if (!fieldValitateObj.validate) continue;
        validateFieldAsyncFn(
          fieldValitateObj.field,
          fieldValitateObj,
          linkedPromises
        );
      }
      let results = [];
      if (validatesPromises.length || linkedPromises.length) {
        results = await Promise.all(validatesPromises);
        await Promise.all(linkedPromises);
      }
      this.setMeta((prev) => ({ ...prev, isValidating: false }));
      for (const linkedField of linkedFields) {
        linkedField.setMeta((prev) => ({ ...prev, isValidating: false }));
      }
      return results.filter(Boolean);
    };
    this.validate = (cause, opts2) => {
      var _a;
      if (!this.state.meta.isTouched) return [];
      const { fieldsErrorMap } = (opts2 == null ? void 0 : opts2.skipFormValidation) ? { fieldsErrorMap: {} } : this.form.validateSync(cause);
      const { hasErrored } = this.validateSync(
        cause,
        fieldsErrorMap[this.name] ?? {}
      );
      if (hasErrored && !this.options.asyncAlways) {
        (_a = this.getInfo().validationMetaMap[getErrorMapKey(cause)]) == null ? void 0 : _a.lastAbortController.abort();
        return this.state.meta.errors;
      }
      const formValidationResultPromise = (opts2 == null ? void 0 : opts2.skipFormValidation) ? Promise.resolve({}) : this.form.validateAsync(cause);
      return this.validateAsync(cause, formValidationResultPromise);
    };
    this.handleChange = (updater) => {
      this.setValue(updater);
    };
    this.handleBlur = () => {
      var _a, _b;
      const prevTouched = this.state.meta.isTouched;
      if (!prevTouched) {
        this.setMeta((prev) => ({ ...prev, isTouched: true }));
        this.validate("change");
      }
      if (!this.state.meta.isBlurred) {
        this.setMeta((prev) => ({ ...prev, isBlurred: true }));
      }
      this.validate("blur");
      (_b = (_a = this.options.listeners) == null ? void 0 : _a.onBlur) == null ? void 0 : _b.call(_a, {
        value: this.state.value,
        fieldApi: this
      });
    };
    this.form = opts.form;
    this.name = opts.name;
    this.timeoutIds = {};
    if (opts.defaultValue !== void 0) {
      this.form.setFieldValue(this.name, opts.defaultValue, {
        dontUpdateMeta: true
      });
    }
    this.store = new store.Derived({
      deps: [this.form.store],
      fn: () => {
        const value = this.form.getFieldValue(this.name);
        const meta = this.form.getFieldMeta(this.name) ?? {
          isValidating: false,
          isTouched: false,
          isBlurred: false,
          isDirty: false,
          isPristine: true,
          errors: [],
          errorMap: {},
          ...opts.defaultMeta
        };
        return {
          value,
          meta
        };
      }
    });
    this.options = opts;
  }
  /**
   * The current field state.
   */
  get state() {
    return this.store.state;
  }
  /**
   * @private
   */
  runValidator(props) {
    const adapters = [
      this.form.options.validatorAdapter,
      this.options.validatorAdapter
    ];
    for (const adapter of adapters) {
      if (adapter && (typeof props.validate !== "function" || "~standard" in props.validate)) {
        return adapter()[props.type](
          props.value,
          props.validate
        );
      }
    }
    if (standardSchemaValidator.isStandardSchemaValidator(props.validate)) {
      return standardSchemaValidator.standardSchemaValidator()()[props.type](
        props.value,
        props.validate
      );
    }
    return props.validate(props.value);
  }
  /**
   * Updates the field's errorMap
   */
  setErrorMap(errorMap) {
    this.setMeta((prev) => ({
      ...prev,
      errorMap: {
        ...prev.errorMap,
        ...errorMap
      }
    }));
  }
}
function normalizeError(rawError) {
  if (rawError) {
    if (typeof rawError !== "string") {
      return "Invalid Form Values";
    }
    return rawError;
  }
  return void 0;
}
function getErrorMapKey(cause) {
  switch (cause) {
    case "submit":
      return "onSubmit";
    case "blur":
      return "onBlur";
    case "mount":
      return "onMount";
    case "server":
      return "onServer";
    case "change":
    default:
      return "onChange";
  }
}
exports.FieldApi = FieldApi;
//# sourceMappingURL=FieldApi.cjs.map

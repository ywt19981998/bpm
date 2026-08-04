(function exposeAuthSessionGeneration(root, factory) {
  const { AuthBusyState, AuthSessionGeneration } = factory();
  root.AuthBusyState = AuthBusyState;
  root.AuthSessionGeneration = AuthSessionGeneration;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { AuthBusyState, AuthSessionGeneration };
  }
})(globalThis, () => {
class AuthSessionGeneration {
  constructor() {
    this.generation = 0;
    this.userId = null;
  }

  activate(user) {
    this.generation += 1;
    this.userId = user ? user.id : null;
    return this.capture();
  }

  clear() {
    return this.activate(null);
  }

  capture() {
    return { generation: this.generation, userId: this.userId };
  }

  isCurrent(snapshot) {
    return Boolean(
      snapshot
      && snapshot.generation === this.generation
      && snapshot.userId === this.userId
    );
  }

  commitIfCurrent(snapshot, commit) {
    if (!this.isCurrent(snapshot)) return false;
    commit();
    return true;
  }
}

class AuthBusyState {
  constructor() {
    this.generation = 0;
    this.busyForms = new Set();
  }

  begin(formId) {
    this.busyForms.add(formId);
    return { generation: this.generation, formId };
  }

  finish(snapshot) {
    if (!snapshot || snapshot.generation !== this.generation) return false;
    this.busyForms.delete(snapshot.formId);
    return true;
  }

  reset() {
    this.generation += 1;
    this.busyForms.clear();
  }

  isBusy(formId) {
    return this.busyForms.has(formId);
  }
}

return { AuthBusyState, AuthSessionGeneration };
});

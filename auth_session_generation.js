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
    this.active = null;
  }

  begin(formId) {
    if (this.active) return null;
    this.active = { generation: this.generation, formId };
    return this.active;
  }

  finish(snapshot) {
    if (!snapshot || snapshot.generation !== this.generation || this.active !== snapshot) return false;
    this.active = null;
    return true;
  }

  reset() {
    this.generation += 1;
    this.active = null;
  }

  isBusy() {
    return Boolean(this.active);
  }
}

return { AuthBusyState, AuthSessionGeneration };
});

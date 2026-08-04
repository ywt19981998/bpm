(function exposeAuthSessionGeneration(root, factory) {
  const AuthSessionGeneration = factory();
  root.AuthSessionGeneration = AuthSessionGeneration;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { AuthSessionGeneration };
  }
})(globalThis, () => class AuthSessionGeneration {
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
});

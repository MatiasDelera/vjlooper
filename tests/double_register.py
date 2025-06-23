import vjlooper

# Register/unregister twice to ensure idempotency
vjlooper.register()
vjlooper.unregister()
vjlooper.register()
vjlooper.unregister()
print("Registered twice without errors")

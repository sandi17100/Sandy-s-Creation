class CheckoutForm:
    def __init__(self, form):
        self.name = form.get("name")
        self.email = form.get("email")
        self.address = form.get("address")

    def validate(self):
        return all([self.name, self.email, self.address])
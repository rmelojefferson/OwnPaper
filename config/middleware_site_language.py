class PublicSiteLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.LANGUAGE_CODE = "pt-br"
        return self.get_response(request)

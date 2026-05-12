class DomainError(Exception):
    pass


class NotFoundError(DomainError):
    pass


class AlreadyExistsError(DomainError):
    pass


class InvalidCredentialsError(DomainError):
    pass


class TenantInactiveError(DomainError):
    pass


class AppointmentConflictError(DomainError):
    pass


class ProviderError(DomainError):
    pass

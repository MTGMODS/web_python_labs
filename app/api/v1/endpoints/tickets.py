"""Бронювання квитків та домашня сторінка пасажира."""

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.models.ticket import Ticket
from app.schemas.booking import PassengerHomeRead, TicketRead
from app.services import booking as booking_service

router = APIRouter(tags=["tickets"])

PASSENGER_ACTIONS = [
    "GET /api/v1/trips — пошук рейсів",
    "GET /api/v1/trips/{trip_id}/seats — схема салону",
    "POST /api/v1/trips/{trip_id}/seats/{seat_number}/hold — забронювати місце",
    "POST /api/v1/tickets/{ticket_id}/pay — оплатити",
    "POST /api/v1/tickets/{ticket_id}/cancel — скасувати",
]


@router.get("/me/home", response_model=PassengerHomeRead, summary="Домашня сторінка пасажира")
def passenger_home(user: CurrentUser, session: SessionDep) -> PassengerHomeRead:
    tickets = booking_service.list_user_tickets(session, user)
    counters = dict.fromkeys(("held", "paid", "cancelled"), 0)
    for ticket in tickets:
        counters[ticket.status.value] += 1

    return PassengerHomeRead(
        role=user.role,
        full_name=user.full_name,
        tickets_total=len(tickets),
        tickets_by_status=counters,
        available_actions=PASSENGER_ACTIONS,
    )


@router.post(
    "/trips/{trip_id}/seats/{seat_number}/hold",
    response_model=TicketRead,
    status_code=status.HTTP_201_CREATED,
    summary="Заблокувати місце на час оформлення",
)
def hold_seat(trip_id: int, seat_number: str, user: CurrentUser, session: SessionDep) -> Ticket:
    return booking_service.hold_seat(session, user, trip_id, seat_number)


@router.get("/tickets/my", response_model=list[TicketRead], summary="Власні квитки")
def my_tickets(user: CurrentUser, session: SessionDep) -> list[Ticket]:
    return booking_service.list_user_tickets(session, user)


@router.post("/tickets/{ticket_id}/pay", response_model=TicketRead, summary="Оплатити квиток")
def pay_ticket(ticket_id: int, user: CurrentUser, session: SessionDep) -> Ticket:
    return booking_service.pay_ticket(session, user, ticket_id)


@router.post(
    "/tickets/{ticket_id}/cancel",
    response_model=TicketRead,
    summary="Скасувати квиток",
)
def cancel_ticket(ticket_id: int, user: CurrentUser, session: SessionDep) -> Ticket:
    return booking_service.cancel_ticket(session, user, ticket_id)

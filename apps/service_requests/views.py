from django.contrib.auth import get_user_model
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit_logs.mixins import AuditActorMixin
from apps.users.permissions import IsDeptHeadOrAdmin, IsStaffRole, effective_role
from .models import RequestStatus, ServiceRequest, TimelineEvent
from .serializers import ServiceRequestSerializer

User = get_user_model()

# Kinds of timeline entry an officer can post from the case page.
UPDATE_KINDS = ('update', 'internal', 'clarification', 'work')


class ServiceRequestViewSet(AuditActorMixin, viewsets.ModelViewSet):
    serializer_class = ServiceRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        role = effective_role(user)
        qs = ServiceRequest.objects.select_related('category', 'category__department').order_by('-submitted_at')

        if role == 'ADMIN':
            return qs
        if role in ('STAFF', 'DEPT_HEAD'):
            if user.department_id:
                return qs.filter(category__department_id=user.department_id)
            return qs.none()
        return qs.filter(citizen=user)

    def perform_create(self, serializer):
        serializer.save(citizen=self.request.user)

    def _author(self, user):
        return user.get_full_name() or user.phone_number

    @action(detail=True, methods=['post'], url_path='status', permission_classes=[IsAuthenticated, IsStaffRole])
    def set_status(self, request, pk=None):
        obj = self.get_object()
        new_status = request.data.get('status')
        note = request.data.get('note', '')

        if new_status not in RequestStatus.values:
            return Response({'status': f'Must be one of {list(RequestStatus.values)}'}, status=400)

        obj.status = new_status
        obj.status_note = note
        if not obj.assigned_department_id:
            obj.assigned_department = obj.category.department
        obj.save()

        TimelineEvent.objects.create(
            request=obj,
            title=f'Status changed to {new_status}',
            body=note,
            author_name=self._author(request.user),
            kind='status',
        )
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['post'], url_path='assign', permission_classes=[IsAuthenticated, IsDeptHeadOrAdmin])
    def assign(self, request, pk=None):
        """
        Routes the request to the department of its category.
        If 'officer' is given, that officer is assigned as well.
        If 'officer' is empty, the department head assigns an officer later.
        """
        obj = self.get_object()
        officer_id = request.data.get('officer')

        if officer_id in (None, ''):
            obj.assigned_department = obj.category.department
            obj.save()
            TimelineEvent.objects.create(
                request=obj,
                title='Routed to department',
                body=f'Routed to {obj.category.department.name}.',
                author_name=self._author(request.user),
                kind='status',
            )
            return Response(self.get_serializer(obj).data)

        try:
            officer = User.objects.get(pk=officer_id, role__in=('STAFF', 'DEPT_HEAD'), is_active=True)
        except (User.DoesNotExist, ValueError, TypeError):
            return Response({'officer': 'Active staff member not found.'}, status=400)

        if officer.department_id != obj.category.department_id:
            return Response({'officer': 'Officer belongs to a different department.'}, status=400)

        obj.assigned_officer = officer
        obj.assigned_department = obj.category.department
        obj.save()

        TimelineEvent.objects.create(
            request=obj,
            title='Assigned to officer',
            body=f'Assigned to {officer.get_full_name() or officer.phone_number}.',
            author_name=self._author(request.user),
            kind='status',
        )
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['post'], url_path='updates', permission_classes=[IsAuthenticated, IsStaffRole])
    def updates(self, request, pk=None):
        """Adds a public update, internal note, clarification or work record to the timeline."""
        obj = self.get_object()
        body = (request.data.get('body') or '').strip()
        kind = request.data.get('kind') or 'update'
        title = (request.data.get('title') or 'Official update').strip()

        if len(body) < 5:
            return Response({'body': 'Write at least 5 characters.'}, status=400)
        if kind not in UPDATE_KINDS:
            return Response({'kind': f'Must be one of {list(UPDATE_KINDS)}'}, status=400)

        TimelineEvent.objects.create(
            request=obj,
            title=title,
            body=body,
            author_name=self._author(request.user),
            kind=kind,
        )
        return Response(self.get_serializer(obj).data, status=201)
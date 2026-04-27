from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .services import (
    proceso_completo,
    obtener_estado_refresh,
    obtener_datasets,
    obtener_workspace,
    es_admin,
    obtener_workspaces,
    obtener_config_completo,
    guardar_config_completo
)


class ProcesoPowerBIView(APIView):

    def post(self, request):

        try:

            fecha_inicial = request.data.get("fechaInicial")
            fecha_final = request.data.get("fechaFinal")
            dataset = request.data.get("dataset")

            workspace = obtener_workspace(request)

            if not fecha_inicial or not fecha_final:
                return Response(
                    {"error": "Debe ingresar ambas fechas"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            proceso_completo(fecha_inicial, fecha_final, dataset, workspace)

            return Response(
                {
                    "mensaje": "Parámetros actualizados y refresh iniciado",
                    "estado": "InProgress"
                },
                status=status.HTTP_202_ACCEPTED
            )

        except Exception as e:

            if "429" in str(e):
                return Response(
                    {"error": "Demasiadas solicitudes. Intente nuevamente en unos segundos."},
                    status=429
                )

            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class RefreshPowerBIStatusView(APIView):

    def get(self, request):

        try:

            dataset = request.GET.get("dataset")
            workspace = obtener_workspace(request)

            estado = obtener_estado_refresh(dataset, workspace)

            return Response(
                estado,
                status=status.HTTP_200_OK,
            )

        except Exception as e:

            if "429" in str(e):
                return Response(
                    {"error": "Demasiadas solicitudes. Intente nuevamente en unos segundos."},
                    status=429
                )

            return Response(
                {"error": "Error en el Servidor, reintente más tarde."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DatasetsView(APIView):

    def get(self, request):

        try:

            workspace = obtener_workspace(request)

            data = {
                "datasets": obtener_datasets(workspace),
                "workspace_actual": workspace,
                "is_admin": es_admin()
            }

            if es_admin():
                data["workspaces"] = obtener_workspaces()

            return Response(data, status=200)

        except Exception as e:

            if "429" in str(e):
                return Response(
                    {"error": "Demasiadas solicitudes. Intente nuevamente en unos segundos."},
                    status=429
                )

            return Response(
                {"error": "Error en el Servidor, reintente más tarde."},
                status=500
            )


class ConfigView(APIView):

    def get(self, request):

        try:

            if not es_admin():
                return Response({"error": "No autorizado"}, status=403)

            config = obtener_config_completo()

            return Response(config, status=200)

        except Exception:
            return Response(
                {"error": "Error obteniendo configuración"},
                status=500
            )

    # 🔥 NUEVO POST
    def post(self, request):

        try:

            if not es_admin():
                return Response({"error": "No autorizado"}, status=403)

            nuevo_config = request.data

            # 🔥 validación mínima
            if not isinstance(nuevo_config, dict):
                return Response({"error": "Formato inválido"}, status=400)

            guardar_config_completo(nuevo_config)

            return Response({"mensaje": "Configuración guardada"}, status=200)

        except ValueError as e:
                    return Response(
                        {"error": str(e)},
                        status=400
                    )
        except Exception:
                    return Response(
                        {"error": "Error guardando configuración"},
                        status=500
                    )
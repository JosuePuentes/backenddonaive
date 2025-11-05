// Ejemplo de uso del componente ModalCrearUsuario
import React, { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "@/components/ui/use-toast";
import ModalCrearUsuario from './ModalCrearUsuario';
import useUsuarios from './useUsuarios';

export function GestionUsuarios() {
  const [usuarios, setUsuarios] = useState([]);
  const { obtenerUsuarios, eliminarUsuario, loading } = useUsuarios();

  // Cargar usuarios al montar el componente
  useEffect(() => {
    cargarUsuarios();
  }, []);

  const cargarUsuarios = async () => {
    try {
      const usuariosData = await obtenerUsuarios();
      setUsuarios(usuariosData);
    } catch (error) {
      toast({
        title: "Error al cargar usuarios",
        description: error.message,
        variant: "destructive",
      });
    }
  };

  const handleUsuarioCreado = () => {
    // Recargar la lista de usuarios
    cargarUsuarios();
  };

  const handleEliminarUsuario = async (id, correo) => {
    if (window.confirm(`¿Estás seguro de que quieres eliminar al usuario ${correo}?`)) {
      try {
        await eliminarUsuario(id);
        toast({
          title: "Usuario eliminado",
          description: `El usuario ${correo} ha sido eliminado correctamente.`,
        });
        cargarUsuarios();
      } catch (error) {
        toast({
          title: "Error al eliminar usuario",
          description: error.message,
          variant: "destructive",
        });
      }
    }
  };

  return (
    <div className="container mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Gestión de Usuarios</h1>
        <ModalCrearUsuario onUsuarioCreado={handleUsuarioCreado} />
      </div>

      {loading ? (
        <div className="text-center py-8">
          <p>Cargando usuarios...</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {usuarios.map((usuario) => (
            <Card key={usuario._id}>
              <CardHeader>
                <div className="flex justify-between items-start">
                  <div>
                    <CardTitle className="text-xl">{usuario.correo}</CardTitle>
                    <p className="text-sm text-gray-600">
                      ID: {usuario._id}
                    </p>
                  </div>
                  <div className="flex space-x-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {/* Implementar edición */}}
                    >
                      Editar
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleEliminarUsuario(usuario._id, usuario.correo)}
                    >
                      Eliminar
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {/* Farmacias asignadas */}
                  <div>
                    <h4 className="font-medium mb-2">Farmacias Asignadas:</h4>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(usuario.farmacias || {}).map(([id, nombre]) => (
                        <Badge key={id} variant="secondary">
                          {nombre} ({id})
                        </Badge>
                      ))}
                    </div>
                  </div>

                  {/* Permisos */}
                  <div>
                    <h4 className="font-medium mb-2">Permisos:</h4>
                    <div className="flex flex-wrap gap-2">
                      {(usuario.permisos || []).map((permiso) => (
                        <Badge key={permiso} variant="outline">
                          {permiso}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {usuarios.length === 0 && !loading && (
        <div className="text-center py-8">
          <p className="text-gray-600">No hay usuarios registrados</p>
        </div>
      )}
    </div>
  );
}

export default GestionUsuarios;

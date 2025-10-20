// Ejemplo de componente para agregar usuario - Solución completa
import React, { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "@/components/ui/use-toast";

export function ModalCrearUsuario({ onUsuarioCreado }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    correo: '',
    contraseña: '',
    farmacias: {},
    permisos: []
  });

  // Lista de farmacias disponibles
  const farmaciasDisponibles = [
    { id: "01", nombre: "Santa Elena" },
    { id: "02", nombre: "Sur America" },
    { id: "03", nombre: "Centro" },
    { id: "04", nombre: "Norte" },
    { id: "05", nombre: "Este" },
    { id: "06", nombre: "Oeste" },
    { id: "07", nombre: "Sur" }
  ];

  // Lista de permisos disponibles
  const permisosDisponibles = [
    { id: "ver_inicio", nombre: "Ver Inicio" },
    { id: "ver_about", nombre: "Ver About" },
    { id: "agregar_cuadre", nombre: "Agregar Cuadre" },
    { id: "ver_cuadres_dia", nombre: "Ver Cuadres del Día" },
    { id: "verificar_cuadres", nombre: "Verificar Cuadres" },
    { id: "editar_cuadre", nombre: "Editar Cuadre" },
    { id: "eliminar_cuadre", nombre: "Eliminar Cuadre" },
    { id: "agregar_gasto", nombre: "Agregar Gasto" },
    { id: "ver_gastos", nombre: "Ver Gastos" },
    { id: "verificar_gastos", nombre: "Verificar Gastos" },
    { id: "editar_gasto", nombre: "Editar Gasto" },
    { id: "eliminar_gasto", nombre: "Eliminar Gasto" },
    { id: "ver_inventario", nombre: "Ver Inventario" },
    { id: "agregar_inventario", nombre: "Agregar Inventario" },
    { id: "editar_inventario", nombre: "Editar Inventario" },
    { id: "eliminar_inventario", nombre: "Eliminar Inventario" },
    { id: "ver_usuarios", nombre: "Ver Usuarios" },
    { id: "crear_usuarios", nombre: "Crear Usuarios" },
    { id: "editar_usuarios", nombre: "Editar Usuarios" },
    { id: "eliminar_usuarios", nombre: "Eliminar Usuarios" },
    { id: "admin_completo", nombre: "Admin Completo" },
    { id: "ver_reportes", nombre: "Ver Reportes" },
    { id: "configurar_sistema", nombre: "Configurar Sistema" }
  ];

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleFarmaciaChange = (farmaciaId, checked) => {
    setFormData(prev => ({
      ...prev,
      farmacias: {
        ...prev.farmacias,
        [farmaciaId]: checked ? farmaciasDisponibles.find(f => f.id === farmaciaId)?.nombre : undefined
      }
    }));
  };

  const handlePermisoChange = (permisoId, checked) => {
    setFormData(prev => ({
      ...prev,
      permisos: checked 
        ? [...prev.permisos, permisoId]
        : prev.permisos.filter(p => p !== permisoId)
    }));
  };

  const crearUsuario = async (datosUsuario) => {
    try {
      const token = localStorage.getItem('token');
      
      const response = await fetch('https://rapifarma-backend.onrender.com/usuarios', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(datosUsuario)
      });
      
      if (response.ok) {
        const resultado = await response.json();
        console.log('Usuario creado exitosamente:', resultado);
        return resultado;
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Error al crear usuario');
      }
    } catch (error) {
      console.error('Error al crear usuario:', error);
      throw error;
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Filtrar farmacias vacías
      const farmaciasFiltradas = Object.fromEntries(
        Object.entries(formData.farmacias).filter(([_, value]) => value)
      );

      const datosUsuario = {
        correo: formData.correo,
        contraseña: formData.contraseña,
        farmacias: farmaciasFiltradas,
        permisos: formData.permisos
      };

      await crearUsuario(datosUsuario);
      
      toast({
        title: "Usuario creado exitosamente",
        description: `El usuario ${formData.correo} ha sido creado correctamente.`,
      });

      // Limpiar formulario
      setFormData({
        correo: '',
        contraseña: '',
        farmacias: {},
        permisos: []
      });

      // Cerrar modal
      setOpen(false);

      // Notificar al componente padre
      if (onUsuarioCreado) {
        onUsuarioCreado();
      }

    } catch (error) {
      toast({
        title: "Error al crear usuario",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>Agregar Usuario</Button>
      </DialogTrigger>
      
      {/* SOLUCIÓN AL ERROR: Agregar DialogDescription */}
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Crear Nuevo Usuario</DialogTitle>
          <DialogDescription>
            Complete el formulario para crear un nuevo usuario en el sistema. 
            El usuario tendrá acceso a las farmacias y permisos seleccionados.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Información básica */}
          <div className="space-y-4">
            <h3 className="text-lg font-medium">Información Básica</h3>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="correo">Correo Electrónico</Label>
                <Input
                  id="correo"
                  type="email"
                  value={formData.correo}
                  onChange={(e) => handleInputChange('correo', e.target.value)}
                  placeholder="usuario@ejemplo.com"
                  required
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="contraseña">Contraseña</Label>
                <Input
                  id="contraseña"
                  type="password"
                  value={formData.contraseña}
                  onChange={(e) => handleInputChange('contraseña', e.target.value)}
                  placeholder="Contraseña segura"
                  required
                />
              </div>
            </div>
          </div>

          {/* Farmacias */}
          <div className="space-y-4">
            <h3 className="text-lg font-medium">Farmacias Asignadas</h3>
            <div className="grid grid-cols-2 gap-4">
              {farmaciasDisponibles.map((farmacia) => (
                <div key={farmacia.id} className="flex items-center space-x-2">
                  <Checkbox
                    id={`farmacia-${farmacia.id}`}
                    checked={!!formData.farmacias[farmacia.id]}
                    onCheckedChange={(checked) => handleFarmaciaChange(farmacia.id, checked)}
                  />
                  <Label htmlFor={`farmacia-${farmacia.id}`}>
                    {farmacia.nombre} ({farmacia.id})
                  </Label>
                </div>
              ))}
            </div>
          </div>

          {/* Permisos */}
          <div className="space-y-4">
            <h3 className="text-lg font-medium">Permisos</h3>
            <div className="grid grid-cols-2 gap-4 max-h-60 overflow-y-auto">
              {permisosDisponibles.map((permiso) => (
                <div key={permiso.id} className="flex items-center space-x-2">
                  <Checkbox
                    id={`permiso-${permiso.id}`}
                    checked={formData.permisos.includes(permiso.id)}
                    onCheckedChange={(checked) => handlePermisoChange(permiso.id, checked)}
                  />
                  <Label htmlFor={`permiso-${permiso.id}`}>
                    {permiso.nombre}
                  </Label>
                </div>
              ))}
            </div>
          </div>

          {/* Botones */}
          <div className="flex justify-end space-x-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={loading}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? "Creando..." : "Crear Usuario"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default ModalCrearUsuario;

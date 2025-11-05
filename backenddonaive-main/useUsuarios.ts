// Hook personalizado para manejar usuarios
import { useState } from 'react';

export const useUsuarios = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const crearUsuario = async (datosUsuario) => {
    setLoading(true);
    setError(null);

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
        return resultado;
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Error al crear usuario');
      }
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const obtenerUsuarios = async () => {
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('token');
      
      const response = await fetch('https://rapifarma-backend.onrender.com/usuarios', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (response.ok) {
        const resultado = await response.json();
        return resultado.usuarios;
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Error al obtener usuarios');
      }
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const actualizarUsuario = async (id, datosUsuario) => {
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('token');
      
      const response = await fetch(`https://rapifarma-backend.onrender.com/usuarios/${id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(datosUsuario)
      });
      
      if (response.ok) {
        const resultado = await response.json();
        return resultado;
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Error al actualizar usuario');
      }
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const eliminarUsuario = async (id) => {
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('token');
      
      const response = await fetch(`https://rapifarma-backend.onrender.com/usuarios/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (response.ok) {
        return true;
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Error al eliminar usuario');
      }
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const obtenerPermisos = async () => {
    try {
      const response = await fetch('https://rapifarma-backend.onrender.com/permisos');
      
      if (response.ok) {
        const resultado = await response.json();
        return resultado;
      } else {
        throw new Error('Error al obtener permisos');
      }
    } catch (err) {
      setError(err.message);
      throw err;
    }
  };

  return {
    loading,
    error,
    crearUsuario,
    obtenerUsuarios,
    actualizarUsuario,
    eliminarUsuario,
    obtenerPermisos
  };
};

export default useUsuarios;

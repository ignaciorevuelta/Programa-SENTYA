import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Users,
  UserPlus,
  UserMinus,
  Clock,
  ArrowLeft,
  Search
} from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { useWorkshopUsers } from '../../hooks/useWorkshopUsers';
import { useWorkshops } from '../../hooks/useWorkshops';
import EnrollUserModal from './EnrollUserModal';
import UnenrollUserModal from './UnenrollUserModal';
import './WorkshopEnrollments.css';

const WorkshopEnrollments = () => {
  const { workshopId } = useParams();
  const navigate = useNavigate();
  const { role } = useAuth();
  const {
    enrolledStudents,
    waitlistStudents,
    loading,
    fetchWorkshopStudents
  } = useWorkshopUsers();
  const { workshops, fetchWorkshops } = useWorkshops();

  const [selectedWorkshop, setSelectedWorkshop] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showEnrollModal, setShowEnrollModal] = useState(false);
  const [showUnenrollModal, setShowUnenrollModal] = useState(false);
  const [selectedEnrollment, setSelectedEnrollment] = useState(null);

  // Permisos
  const canManageEnrollments = ['administrator', 'coordinator'].includes(role);
  const canEnrollUsers = canManageEnrollments || role === 'professional';

  // Función para determinar ruta de vuelta según rol
  const getBackRoute = () => {
    if (role === 'administrator' || role === 'coordinator') {
      return '/workshops';
    }
    if (role === 'professional' || role === 'client') {
      return '/my-workshops';
    }
    return '/workshops';
  };

  useEffect(() => {
    if (workshopId) {
      fetchWorkshopStudents(parseInt(workshopId));
      fetchWorkshops().then(response => {
        if (response?.workshops) {
          const workshop = response.workshops.find(w => w.id === parseInt(workshopId));
          setSelectedWorkshop(workshop);
        }
      });
    }
  }, [workshopId, fetchWorkshopStudents, fetchWorkshops]);

  // Filtrar estudiantes por búsqueda
  const filteredEnrolled = enrolledStudents.filter(enrollment => {
    const userName = enrollment.user_name?.toLowerCase() || '';
    const query = searchQuery.toLowerCase();
    return userName.includes(query);
  });

  const filteredWaitlist = waitlistStudents.filter(enrollment => {
    const userName = enrollment.user_name?.toLowerCase() || '';
    const query = searchQuery.toLowerCase();
    return userName.includes(query);
  });

  const handleUnenroll = (enrollment) => {
    setSelectedEnrollment(enrollment);
    setShowUnenrollModal(true);
  };

  if (loading && enrolledStudents.length === 0) {
    return (
      <div className="enrollments-loading">
        <div className="loading-spinner"></div>
        <p>Cargando inscripciones...</p>
      </div>
    );
  }

  return (
    <div className="enrollments-view">
      {/* Botón Volver */}
      <button className="btn-back" onClick={() => navigate(getBackRoute())}>
        <ArrowLeft size={20} />
        Volver a Talleres
      </button>

      {/* Header */}
      <div className="enrollments-header">
        <div className="header-info">
          <h1>{selectedWorkshop ? `Inscripciones: ${selectedWorkshop.name}` : 'Inscripciones'}</h1>
          <p className="subtitle">
            {canManageEnrollments ? 'Gestiona los usuarios inscritos' : 'Visualiza los usuarios inscritos'}
          </p>
        </div>

        {canEnrollUsers && (
          <button className="btn-enroll" onClick={() => setShowEnrollModal(true)}>
            <UserPlus size={20} />
            <span>Inscribir Usuario</span>
          </button>
        )}
      </div>

      {/* Barra de capacidad */}
      {selectedWorkshop && (
        <div className="capacity-section">
          <div className="capacity-info">
            <span className="capacity-label">Capacidad:</span>
            <span className="capacity-numbers">
              {selectedWorkshop.current_capacity} / {selectedWorkshop.max_capacity}
            </span>
          </div>
          <div className="capacity-progress">
            <div
              className="capacity-fill"
              style={{
                width: `${(selectedWorkshop.current_capacity / selectedWorkshop.max_capacity) * 100}%`,
                backgroundColor: selectedWorkshop.current_capacity >= selectedWorkshop.max_capacity
                  ? '#ef4444'
                  : '#10b981'
              }}
            />
          </div>
          <div className="capacity-status">
            {selectedWorkshop.current_capacity >= selectedWorkshop.max_capacity ? (
              <span className="status-full">🔴 Taller Lleno</span>
            ) : (
              <span className="status-available">
                ✅ {selectedWorkshop.max_capacity - selectedWorkshop.current_capacity} cupos disponibles
              </span>
            )}
          </div>
        </div>
      )}

      {/* Stats cards */}
      <div className="enrollments-stats">
        <div className="stat-card">
          <div className="stat-icon enrolled">
            <Users size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{enrolledStudents.length}</span>
            <span className="stat-label">Inscritos</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon waitlist">
            <Clock size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{waitlistStudents.length}</span>
            <span className="stat-label">En Espera</span>
          </div>
        </div>
      </div>

      {/* Búsqueda */}
      <div className="search-container">
        <Search size={20} />
        <input
          type="text"
          placeholder="Buscar por nombre de usuario..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      {/* Estudiantes inscritos */}
      <section className="enrollments-section">
        <div className="section-header">
          <h2>
            <Users size={20} />
            Usuarios Inscritos ({filteredEnrolled.length})
          </h2>
        </div>

        {filteredEnrolled.length === 0 ? (
          <div className="empty-state">
            <Users size={48} />
            <p>No hay estudiantes inscritos</p>
            {canEnrollUsers && (
              <button className="btn-enroll-empty" onClick={() => setShowEnrollModal(true)}>
                <UserPlus size={20} />
                Inscribir Primer Usuario
              </button>
            )}
          </div>
        ) : (
          <div className="students-grid">
            {filteredEnrolled.map(enrollment => (
              <div key={enrollment.id} className="student-card">
                <div className="student-main">
                  <div className="student-avatar">
                    {enrollment.user_name?.charAt(0).toUpperCase()}
                  </div>
                  <div className="student-content">
                    <h3 className='students-subtitle'>{enrollment.user_name}</h3>
                    <p>Inscrito: {new Date(enrollment.assignment_date).toLocaleDateString('es-ES')}</p>
                  </div>
                </div>
                {canManageEnrollments && (
                  <button
                    className="btn-unenroll"
                    onClick={() => handleUnenroll(enrollment)}
                    title="Desinscribir usuario"
                  >
                    <UserMinus size={16} />
                    <span>Desinscribir</span>
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Lista de espera */}
      {waitlistStudents.length > 0 && (
        <section className="enrollments-section">
          <div className="section-header">
            <h2>
              <Clock size={20} />
              Lista de Espera ({filteredWaitlist.length})
            </h2>
          </div>

          <div className="students-grid">
            {filteredWaitlist.map(enrollment => (
              <div key={enrollment.id} className="student-card student-card-waitlist">
                <span className="waitlist-badge">#{enrollment.waitlist_position}</span>
                <div className="student-main">
                  <div className="student-avatar student-avatar-waitlist">
                    {enrollment.user_name?.charAt(0).toUpperCase()}
                  </div>
                  <div className="student-content">
                    <h3>{enrollment.user_name}</h3>
                    <p>En espera desde: {new Date(enrollment.assignment_date).toLocaleDateString('es-ES')}</p>
                  </div>
                </div>
                {canManageEnrollments && (
                  <button
                    className="btn-unenroll"
                    onClick={() => handleUnenroll(enrollment)}
                    title="Eliminar de lista de espera"
                  >
                    <UserMinus size={16} />
                    <span>Eliminar</span>
                  </button>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Modales */}
      {canEnrollUsers && showEnrollModal && (
        <EnrollUserModal
          workshopId={parseInt(workshopId)}
          workshopName={selectedWorkshop?.name}
          onClose={() => setShowEnrollModal(false)}
          onSuccess={() => {
            setShowEnrollModal(false);
            fetchWorkshopStudents(parseInt(workshopId));
          }}
        />
      )}

      {showUnenrollModal && selectedEnrollment && (
        <UnenrollUserModal
          enrollment={selectedEnrollment}
          onClose={() => {
            setShowUnenrollModal(false);
            setSelectedEnrollment(null);
          }}
          onSuccess={() => {
            setShowUnenrollModal(false);
            setSelectedEnrollment(null);
            fetchWorkshopStudents(parseInt(workshopId));
          }}
        />
      )}
    </div>
  );
};

export default WorkshopEnrollments;